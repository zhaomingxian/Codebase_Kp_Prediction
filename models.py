##
#
##

import os
import pandas as pd
import datetime as dt
import numpy as np
import multiprocessing
from multiprocessing import Pool
import threading
import traceback

import util
import database as db
from filelock import FileLock
from sklearn.preprocessing import MinMaxScaler

# Keras
from keras.optimizers import Adagrad, Adam, SGD, RMSprop
from keras.callbacks import EarlyStopping
from kgp.utils.assemble import load_NN_configs, load_GP_configs, assemble
from kgp.utils.experiment import train
from kgp.losses import gen_gp_loss

is_hing = True
is_goes_data = False
np.random.seed(0)

global lock
lock = multiprocessing.Lock()

os.environ["GPML_PATH"] = "/home/shibaji7/anaconda3/envs/deep/lib/python2.7/site-packages/kgp/backend/gpml/"

def store_prediction_to_file(fname,dn,y_obs,y_pred,pr_c,prT,model):
    global lock
    with lock:
        if not os.path.exists(fname):
            with open(fname, "a+") as f: f.write("dn,y_obs,y_pred,prob_clsf,probT,model\n")
        with open(fname, "a+") as f: f.write("%s,%.2f,%.2f,%.2f,%.2f,%s\n"%(dn.strftime("%Y-%m-%d %H:%M:%S"),y_obs,y_pred,pr_c,prT,model))
        pass
    return

def store_to_file(fname,dn,y_obs,y_pred,std,pr,prt,model):
    global lock
    with lock:
        if not os.path.exists(fname): 
            with open(fname, "a+") as f: f.write("dn,y_obs,y_pred,lb,ub,prob_clsf,probT,model\n")
        with open(fname, "a+") as f: f.write("%s,%.2f,%.2f,%.2f,%.2f,%.2f,%.2f,%s\n"%(dn.strftime("%Y-%m-%d %H:%M:%S"),y_obs,y_pred,y_pred-std,y_pred+std,pr,prt,model))
        pass
    return

def store_deepgp_prediction_to_file(fname,dn,y_obs,y_pred,sigma,pr_c,prT,model):
    global lock
    with lock:
        if not os.path.exists(fname):
            with open(fname, "a+") as f: f.write("dn,y_obs,y_pred,lb,ub,prob_clsf,probT,model\n")
        with open(fname, "a+") as f: f.write("%s,%.2f,%.2f,%.2f,%.2f,%.2f,%.2f,%s\n"%(dn.strftime("%Y-%m-%d %H:%M:%S"),y_obs,y_pred,y_pred-sigma,y_pred+sigma,pr_c,prT,model))
        pass
    return

def store_prediction_to_loc_file(fname,dn,y_obs,y_pred,pr_c,prT,model):
    with FileLock(fname):
        if not os.path.exists(fname):
            with open(fname, "a+") as f: f.write("dn,y_obs,y_pred,prob_clsf,probT,model\n")
        with open(fname, "a+") as f: f.write("%s,%.2f,%.2f,%.2f,%.2f,%s\n"%(dn.strftime("%Y-%m-%d %H:%M:%S"),y_obs,y_pred,pr_c,prT,model))
        pass
    return


class GPRModelPerDataPoint(threading.Thread):
    def __init__(self, y, reg_det, clf, dn, data, alt_win):
        threading.Thread.__init__(self)
        self.y = y
        self.reg = reg_det[0]
        self.clf = clf
        self.dn = dn
        self.data = data
        self.trw = reg_det[2]
        self.mI = 1
        self.model = reg_det[1]
        self.alt_win = alt_win
        self.fname = "out/storm/det.%s.pred.%d.csv"%(self.model,self.trw)
        if is_goes_data: self.fname = "out/storm/det.%s.goes.%d.csv"%(self.model,self.trw)
        return

    def data_windowing(self, trw=None, isLW = False):
        _o = self.data[0]
        _xparams = self.data[1]
        _yparam = self.data[2]
        if trw is None: trw = self.trw
        print trw
        _tstart = self.dn - dt.timedelta(days=trw) # training window start inclusive
        _tend = self.dn - dt.timedelta(hours=3) # training window end inclusive
        self._o_train = _o[(_o["Date_WS"] >= _tstart) & (_o["Date_WS"] <= _tend)]
        self._o_test = _o[(_o["Date_WS"] == self._pred_point_time)]
        if isLW: 
            _o_train = self._o_train[self._o_train[_yparam] >= 4.5]
            if  np.count_nonzero(_o_train.as_matrix(_xparams)) == 0: self._o_train = _o_train
            pass
        return

    def run(self):
        prt = 0.5
        print("-->Process for date:%s"%self.dn)
        _xparams = self.data[1]
        _yparam = self.data[2]
        mI = self.mI
        reg = self.reg
        clf = self.clf
        self._forecast_time = self.dn + dt.timedelta(hours = (mI*3))
        self._pred_point_time = self.dn # Time at which forecast is taking place
        self.data_windowing()
        _o_train = self._o_train
        _o_test = self._o_test
        X_test = _o_test.as_matrix(_xparams)
        self.y_obs = -1
        self.y_pred = -1
        self.std = -1
        self.pr = -1
        self.prt = prt
        if _o_test.shape[0] == 1:
            try:
                X_train = _o_train.as_matrix(_xparams)
                y_train = np.array(_o_train[_yparam]).reshape(len(_o_train),1)
                X_test = _o_test.as_matrix(_xparams)
                y_test = np.array(_o_test[_yparam]).reshape(len(_o_test),1)
                self.y_obs = y_test[0,0]
                pr = clf.predict_proba(X_test)[0,0]
                self.pr = pr
                if pr > prt:
                    #self.data_windowing(self.trw*self.alt_win, True)
                    self.data_windowing(self.alt_win, True)
                    _o_train = self._o_train
                    print(self.dn,pr,self.alt_win)
                    X_train = _o_train.as_matrix(_xparams)
                    y_train = np.array(_o_train[_yparam]).reshape(len(_o_train),1)
                    pass
                print X_train.size, y_train.size
                reg.fit(X_train, y_train)
                if len(reg.predict(X_test).shape) == 2: 
                    uu, std = reg.predict(X_test,return_std=True)
                    print uu, std
                    self.y_pred, self.std = uu[0,0], std[0]
                    #self.y_pred = reg.predict(X_test)
                    pass
                else: 
                    uu, std = reg.predict(X_test,return_std=True)
                    self.y_pred, self.std = uu[0], std[0]
                    #self.y_pred = reg.predict(X_test)
                    pass
            except: 
                print(self.dn)
                traceback.print_exc()
            pass
        else: pass
        print(self.y_obs,self.y_pred)
        store_to_file(self.fname,self.dn,self.y_obs,self.y_pred,self.std,self.pr,self.prt,self.model)
        return

class ModelPerDataPoint(threading.Thread):
    def __init__(self, y, reg_det, clf, dn, data, alt_win):
        threading.Thread.__init__(self)
        self.y = y
        self.reg = reg_det[0]
        self.clf = clf
        self.dn = dn
        self.data = data
        self.trw = reg_det[2]
        self.mI = 1
        self.model = reg_det[1]
        self.alt_win = alt_win
        #self.fname = "out/det.%s.pred.%d.gm.csv"%(self.model,self.trw)
        self.fname = "out/storm/det.%s.pred.%d.csv"%(self.model,self.trw)
        if is_goes_data: self.fname = "out/storm/det.%s.goes.%d.csv"%(self.model,self.trw)
        if is_hing: self.fname = "out/storm/hing/det.%s.pred.%d.csv"%(self.model,self.trw)
        return

    def data_windowing(self, trw=None, isLW = False):
        _o = self.data[0]
        _xparams = self.data[1]
        _yparam = self.data[2]
        if trw is None: trw = self.trw
        print trw
        _tstart = self.dn - dt.timedelta(days=trw) # training window start inclusive
        _tend = self.dn - dt.timedelta(hours=3) # training window end inclusive
        self._o_train = _o[(_o["Date_WS"] >= _tstart) & (_o["Date_WS"] <= _tend)]
        self._o_test = _o[(_o["Date_WS"] == self._pred_point_time)]
        if isLW: 
            _o_train = self._o_train[self._o_train[_yparam] >= 4.5]
            if  np.count_nonzero(_o_train.as_matrix(_xparams)) == 0: self._o_train = _o_train
            pass
        return

    def run(self):
        prt = 0.5
        print("-->Process for date:%s"%self.dn)
        _xparams = self.data[1]
        _yparam = self.data[2]
        mI = self.mI
        reg = self.reg
        clf = self.clf
        self._forecast_time = self.dn + dt.timedelta(hours = (mI*3))
        self._pred_point_time = self.dn # Time at which forecast is taking place
        self.data_windowing()
        _o_train = self._o_train
        _o_test = self._o_test
        X_test = _o_test.as_matrix(_xparams)
        self.y_obs = -1
        self.y_pred = -1
        self.std = -1
        self.pr = -1
        self.prt = prt
        if _o_test.shape[0] == 1:
            try:
                X_train = _o_train.as_matrix(_xparams)
                y_train = np.array(_o_train[_yparam]).reshape(len(_o_train),1)
                X_test = _o_test.as_matrix(_xparams)
                y_test = np.array(_o_test[_yparam]).reshape(len(_o_test),1)
                self.y_obs = y_test[0,0]
                pr = clf.predict_proba(X_test)[0,0]
                #pr = clf.predict_proba(X_test[:,:-2])[0,0]
                self.pr = pr
                if pr > prt:
                    #self.data_windowing(self.trw*self.alt_win, True)
                    self.data_windowing(self.alt_win, True)
                    _o_train = self._o_train
                    print(self.dn,pr,self.alt_win)
                    X_train = _o_train.as_matrix(_xparams)
                    y_train = np.array(_o_train[_yparam]).reshape(len(_o_train),1)
                    pass
                print X_train.size, y_train.size
                reg.fit(X_train, y_train)
                if len(reg.predict(X_test).shape) == 2: 
                    #uu, std = reg.predict(X_test,return_std=True)
                    #print uu, std
                    #self.y_pred, self.std = uu[0,0], std[0]
                    self.y_pred = reg.predict(X_test)
                    pass
                else: 
                    #uu, std = reg.predict(X_test,return_std=True)
                    #self.y_pred, self.std = uu[0], std[0]
                    self.y_pred = reg.predict(X_test)
                    pass
            except: 
                print(self.dn)
                traceback.print_exc()
            pass
        else: pass
        print(self.y_obs,self.y_pred)
        if self.model == "": store_prediction_to_loc_file(self.fname,self.dn,self.y_obs,self.y_pred,self.pr,self.prt,self.model)
        else: 
            store_prediction_to_file(self.fname,self.dn,self.y_obs,self.y_pred,self.pr,self.prt,self.model)
            #store_to_file(self.fname,self.dn,self.y_obs,self.y_pred,self.std,self.pr,self.prt,self.model)
        return

def run_model_per_year(details):
    y = details[0]
    reg = details[1]
    clf = details[2]
    data = details[3]
    alt_win = details[4]
    N = 8*30*8
    _dates = [dt.datetime(y,2,1) + dt.timedelta(hours=i*3) for i in range(N)]
    print("-->Process for year:%d"%y)
    for dn in _dates: 
        th = ModelPerDataPoint(y,reg,clf,dn,data,alt_win)
        th.start()
        pass
    return


###
# GLM
###
def run_model_based_on_deterministic_algoritms(Y, model, trw=27):
    print("--> Loading data...")
    #_o, _xparams, _yparam = db.load_data_for_deterministic_reg()
    _o, _xparams, _yparam = db.load_data_with_goes_for_deterministic_reg()
    f_clf = "out/rf.pkl"
    clf = util.get_best_determinsistic_classifier(f_clf)
    reg = util.get_regressor(model, trw)
    years = range(Y,Y+1)
    regs = [reg] * len(years)
    clfs = [clf] * len(years)
    alt_wins = [10] * len(years)
    data_array = [(_o, _xparams, _yparam)] * len(years)
    _a = []
    for x,y,z,k,aw in zip(years, regs, clfs, data_array, alt_wins): _a.append((x,y,z,k,aw))
    year_pool = Pool(10)
    year_pool.map(run_model_per_year, _a)
    return

def run_process_model_per_date(details):
    y = details[0]
    reg = details[1]
    clf = details[2]
    dn = details[3]
    data = details[4]
    alt_win = details[5]
    th = ModelPerDataPoint(y,reg,clf,dn,data,alt_win)
    th.run()
    return

def run_model_process_based_on_deterministic_algoritms(Y, model, trw=27):
    _o, _xparams, _yparam = db.load_data_for_deterministic_reg()
    f_clf = "out/rf.pkl"
    clf = util.get_best_determinsistic_classifier(f_clf)
    reg = util.get_regressor(model, trw)
    N = 8*30*8
    _dates = [dt.datetime(Y,2,1) + dt.timedelta(hours=i*3) for i in range(N)]
    print("-->Process for year:%d"%Y)
    years = [Y] * len(_dates)
    regs = [reg] * len(_dates)
    clfs = [clf] * len(_dates)
    alt_wins = [10] * len(_dates)
    data_array = [(_o, _xparams, _yparam)] * len(_dates)
    _a = []
    for x,y,z,dn,k,aw in zip(years, regs, clfs, _dates, data_array, alt_wins): _a.append((x,y,z,dn,k,aw))
    date_pool = Pool(12)
    date_pool.map(run_process_model_per_date, _a)    
    return

###
# GP models
###
def run_gp_model_per_date(details):
    y = details[0]
    reg = details[1]
    clf = details[2]
    dn = details[3]
    data = details[4]
    alt_win = details[5]
    th = ModelPerDataPoint(y,reg,clf,dn,data,alt_win)
    th.run()
    return

def run_model_based_on_gp(Y, kt = "RQ", model="GPR", trw=27):
    print("--> Loading data...")
    _o, _xparams, _yparam = db.load_data_for_deterministic_reg()
    f_clf = "out/rf.pkl"
    clf = util.get_best_determinsistic_classifier(f_clf)
    hyp = util.get_hyp_param(kt)
    reg = util.get_gpr(kt, hyp, nrst = 10, trw=27)
    N = 8*30*3
    _dates = [dt.datetime(Y,7,1) + dt.timedelta(hours=i*3) for i in range(N)]
    print("-->Process for year:%d"%Y)
    years = [Y] * len(_dates)
    regs = [reg] * len(_dates)
    clfs = [clf] * len(_dates)
    alt_wins = [36] * len(_dates)
    data_array = [(_o, _xparams, _yparam)] * len(_dates)
    _a = []
    for x,y,z,dn,k,aw in zip(years, regs, clfs, _dates, data_array, alt_wins): _a.append((x,y,z,dn,k,aw))
    date_pool = Pool(1)
    date_pool.map(run_gp_model_per_date, _a)
    return


###
#  LSTM model
###
class LSTMPerDataPoint(object):
    def __init__(self, y, reg_det, clf, dn, data, alt_win, look_back):
        self.y = y
        self.reg = reg_det[0]
        self.clf = clf
        self.dn = dn
        self.data = data
        self.trw = reg_det[2]
        self.mI = 1
        self.model = reg_det[1]
        self.alt_win = alt_win
        self.fname = "out/storm/det.%s.pred.%d.csv"%(self.model,self.trw)
        if is_goes_data: self.fname = "out/storm/det.%s.goes.%d.csv"%(self.model,self.trw)
        self.sclX = MinMaxScaler(feature_range=(0, 1))
        self.sclY = MinMaxScaler(feature_range=(0, 1))
        self.look_back = look_back
        return

    def data_windowing(self, trw=None, isLW = False):
        _o = self.data[0]
        _xparams = self.data[1]
        _yparam = self.data[2]
        print self.trw
        if trw is None: trw = self.trw
        _tstart = self.dn - dt.timedelta(days=trw) # training window start inclusive
        _tend = self.dn # training window end inclusive
        _o_all = _o[(_o["Date_WS"] >= _tstart) & (_o["Date_WS"] <= _tend)]
        if isLW: _o_all = _o_all[_o_all[_yparam] >= 4.5]
        _o_test  = _o_all[_o_all["Date_WS"]==self.dn]
        T = False
        if len(_o_test) == 1:
            X,y = _o_all[_xparams].as_matrix(), _o_all[_yparam].as_matrix()
            Xm,ym = self.txXY(X,y)
            self.X_test, self.y_test = Xm[-1,:], ym[-1,0]
            self.X_train, self.y_train  = Xm[:-1,:], ym[:-1,0].reshape((len(ym)-1,1))
            self.X_train = np.reshape(self.X_train, (self.X_train.shape[0], self.look_back, self.X_train.shape[2]))
            self.y_obs = self.reY([[self.y_test]])[0,0]
            #print(self.X_test.shape)
            self.X_test_lstm = np.reshape(self.X_test, (1, self.look_back, self.X_test.shape[1]))
            print(self.X_train.shape,self.y_train.shape, self.X_test.shape)
            T = True
            pass
        return T

    def create_dataset(self,X,y, look_back=1):
        dataX, dataY = [], []
        for i in range(look_back+1,len(X)):
            a = X[i-look_back:i, :]
            dataX.append(a)
            dataY.append(y[i].tolist())
            pass
        return np.array(dataX), np.array(dataY)
    

    def txXY(self, X, y):
        Xs = self.sclX.fit_transform(X)
        ys = self.sclY.fit_transform(y)
        Xm,ym = self.create_dataset(Xs,ys,self.look_back)
        return Xm,ym

    def reY(self, y):
        y = self.sclY.inverse_transform(y)
        return y

    def run(self):
        prt = 0.7
        print("-->Process for date:%s"%self.dn)
        _xparams = self.data[1]
        _yparam = self.data[2]
        mI = self.mI
        reg = self.reg
        clf = self.clf
        self._forecast_time = self.dn + dt.timedelta(hours = (mI*3))
        self._pred_point_time = self.dn # Time at which forecast is taking place
        self.y_obs = -1
        self.y_pred = -1
        self.pr = -1
        self.prt = prt
        if self.data_windowing():
            X_train,y_train = self.X_train,self.y_train
            X_test,y_test = self.X_test,self.y_test
            #print("shape:",X_test[:,:].shape)
            try:
                pr = clf.predict_proba(X_test[:,:-2])[0,0]
                #pr = clf.predict_proba(X_test[:,:])[0,0]
                self.pr = pr
                if pr > prt:
                    self.data_windowing(self.trw*self.alt_win, True)
                    X_train,y_train = self.X_train,self.y_train
                    pass
                reg.fit(X_train, y_train, batch_size = 2, epochs = 50, verbose = 0)
                if len(reg.predict(self.X_test_lstm).shape) == 2: self.y_pred = self.reY(reg.predict(self.X_test_lstm)[0,0])[0,0]
                else: self.y_pred = self.reY(reg.predict(self.X_test_lstm)[0])[0,0]
            except: 
                print(self.dn)
                traceback.print_exc()
            pass
        else: pass
        print(self.y_obs,self.y_pred,self.fname)
        store_prediction_to_file(self.fname,self.dn,self.y_obs,self.y_pred,self.pr,self.prt,self.model)
        print("Done")
        return


def run_lstm_model_per_date(details):
    y = details[0]
    reg_details = details[1]
    look_back = reg_details[1]
    reg = util.get_lstm(ishape=reg_details[0],look_back=reg_details[1],trw=reg_details[2])
    clf = details[2]
    dn = details[3]
    data = details[4]
    alt_win = details[5]
    th = LSTMPerDataPoint(y,reg,clf,dn,data,alt_win,look_back)
    th.run()
    return

def run_model_based_on_lstm(Y, model="LSTM", trw=27):
    print("--> Loading data...")
    #_o, _xparams, _yparam = db.load_data_for_deterministic_reg()
    _o, _xparams, _yparam = db.load_data_with_goes_for_deterministic_reg()
    f_clf = "out/rf.pkl"
    clf = util.get_best_determinsistic_classifier(f_clf)
    reg = (10,1,trw)
    reg = (14,10,trw)
    N = 8*30*8
    #N = 1
    _dates = [dt.datetime(Y,2,1) + dt.timedelta(hours=i*3) for i in range(N)]
    print("-->Process for year:%d"%Y)
    years = [Y] * len(_dates)
    regs = [reg] * len(_dates)
    clfs = [clf] * len(_dates)
    alt_wins = [36] * len(_dates)
    data_array = [(_o, _xparams, _yparam)] * len(_dates)
    _a = []
    for x,y,z,dn,k,aw in zip(years, regs, clfs, _dates, data_array, alt_wins): _a.append((x,y,z,dn,k,aw))
    date_pool = Pool(8)
    date_pool.map(run_lstm_model_per_date, _a)
    return

##
# Deep GP
##
def build_lstmgp(input_shape, gp_input_shape, nb_outputs, batch_size, nb_train_samples):
    nn_params = {
        'H_dim': 16,
        'H_activation': 'tanh',
        'dropout': 0.1,
    }
    gp_params = {
        'cov': 'SEiso',
        'hyp_lik': -1.0,
        'hyp_cov': [[1.], [0.0]],
        'opt': {},
    }

    nn_configs = load_NN_configs(filename='lstm.yaml',
                                 input_shape=input_shape,
                                 output_shape=gp_input_shape,
                                 params=nn_params)
    gp_configs = load_GP_configs(filename='gp.yaml',
                                 nb_outputs=nb_outputs,
                                 batch_size=batch_size,
                                 nb_train_samples=nb_train_samples,
                                 params=gp_params)

    # Construct & compile the model
    model = assemble('GP-LSTM', [nn_configs['1H'], gp_configs['GP']])
    loss = [gen_gp_loss(gp) for gp in model.output_gp_layers]
    model.compile(optimizer=Adam(1e-2), loss=loss)

    return model

def build_lstmgpt(input_shape, gp_input_shape, nb_outputs, batch_size, nb_train_samples):
    nn_params = {
            'H_dim': 16,
            'H_activation': 'tanh',
            'dropout': 0.1,
            }
    gp_params = {
            'cov': 'RQiso',
            'hyp_lik': -1.0,
            'hyp_cov': [[1.],[1.], [0.0]],
            'opt': {},
            }
    
    nn_configs = load_NN_configs(filename='lstm.yaml',
            input_shape=input_shape,
            output_shape=gp_input_shape,
            params=nn_params)
    gp_configs = load_GP_configs(filename='gp.yaml',
            nb_outputs=nb_outputs,
            batch_size=batch_size,
            nb_train_samples=nb_train_samples,
            params=gp_params)
    
    # Construct & compile the model
    model = assemble('GP-LSTM', [nn_configs['2H'], gp_configs['GP']])
    loss = [gen_gp_loss(gp) for gp in model.output_gp_layers]
    model.compile(optimizer=Adam(1e-2), loss=loss)
    
    return model


class DeepGPPerDataPoint(object):
    def __init__(self, y, reg_det, clf, dn, data, alt_win, look_back):
        self.y = y
        self.reg = reg_det[0]
        self.clf = clf
        self.dn = dn
        self.data = data
        self.trw = reg_det[2]
        self.mI = 1
        self.model = "deepGP"
        self.alt_win = alt_win
        self.fname = "out/storm/det.%s.pred.%d.csv"%(self.model,self.trw)
        if is_goes_data: self.fname = "out/storm/det.%s.goes.%d.csv"%(self.model,self.trw)
        print self.fname
        self.sclX = MinMaxScaler(feature_range=(0, 1))
        self.sclY = MinMaxScaler(feature_range=(0, 1))
        self.look_back = look_back
        return

    def data_windowing(self, trw=None, isLW = False):
        _o = self.data[0]
        _xparams = self.data[1]
        _yparam = self.data[2]
        if trw is None: trw = self.trw
        _tstart = self.dn - dt.timedelta(days=trw) # training window start inclusive
        _tend = self.dn # training window end inclusive
        _o_all = _o[(_o["Date_WS"] >= _tstart) & (_o["Date_WS"] <= _tend)]
        if isLW: _o_all = _o_all[_o_all[_yparam] >= 4.5]
        _o_test  = _o_all[_o_all["Date_WS"]==self.dn]
        T = False
        if len(_o_test) == 1:
            X,y = _o_all[_xparams].as_matrix(), _o_all[_yparam].as_matrix()
            Xm,ym = self.txXY(X,y)
            print(Xm.shape,ym.shape)
            self.X_test, self.y_test = Xm[-1,:], ym[-1,0]
            print(Xm.shape,ym.shape)
            self.X_train, self.y_train  = Xm[:-1,:], ym[:-1,0].reshape((len(ym)-1,1))
            self.X_train = np.reshape(self.X_train, (self.X_train.shape[0], self.look_back, self.X_train.shape[2]))
            self.y_obs = self.reY([[self.y_test]])[0,0]
            self.X_test_lstm = np.reshape(self.X_test, (1, self.look_back, self.X_test.shape[1]))
            self.DD = {
                'train': [self.X_train, np.reshape(self.y_train, (len(self.y_train),1,1))],
                'test': [self.X_test_lstm, np.reshape(self.y_test, (1,1,1))],
            }
            # Re-format targets
            for set_name in self.DD:
                ky = self.DD[set_name][1]
                ky = ky.reshape((-1, 1, np.prod(ky.shape[1:])))
                self.DD[set_name][1] = [ky[:,:,i] for i in xrange(ky.shape[2])]
                pass
            print(self.DD["train"][0].shape, np.array(self.DD["train"][1]).shape)
            # Model & training parameters
            self.nb_train_samples = self.DD['train'][0].shape[0]
            self.input_shape = list(self.DD['train'][0].shape[1:])
            self.nb_outputs = len(self.DD['train'][1])
            self.gp_input_shape = (1,)
            self.batch_size = 128
            self.epochs = 20
            self.reg = build_lstmgp(self.input_shape, self.gp_input_shape, self.nb_outputs, self.batch_size, self.nb_train_samples)
            T = True
            pass
        return T

    def create_dataset(self,X,y, look_back=1):
        dataX, dataY = [], []
        for i in range(look_back+1,len(X)):
            a = X[i-look_back:i, :]
            dataX.append(a)
            dataY.append(y[i].tolist())
            pass
        return np.array(dataX), np.array(dataY)
    

    def txXY(self, X, y):
        Xs = self.sclX.fit_transform(X)
        ys = self.sclY.fit_transform(y)
        Xm,ym = self.create_dataset(Xs,ys,self.look_back)
        return Xm,ym

    def reY(self, y):
        y = self.sclY.inverse_transform(y)
        return y

    def run(self):
        prt = 0.5
        print("-->Process for date:%s"%self.dn)
        _xparams = self.data[1]
        _yparam = self.data[2]
        mI = self.mI
        reg = self.reg
        clf = self.clf
        self._forecast_time = self.dn + dt.timedelta(hours = (mI*3))
        self._pred_point_time = self.dn # Time at which forecast is taking place
        self.y_obs = -1
        self.y_pred = -1
        self.pr = -1
        self.sigma = 0.
        self.prt = prt
        
        if self.data_windowing():
            X_test,y_test = self.X_test,self.y_test
            try:
                pr = clf.predict_proba(X_test[:,:-4])[0,0]
                self.pr = pr
                if pr > prt: self.data_windowing(self.trw*self.alt_win, True)
                # Callbacks
                callbacks = [EarlyStopping(monitor='mse', patience=10)]
                
                # Train the model
                history = train(self.reg, self.DD, callbacks=callbacks, gp_n_iter=5,
                    checkpoint='lstm', checkpoint_monitor='mse',
                    epochs=self.epochs, batch_size=self.batch_size, verbose=0)
                
                # Finetune the model
                self.reg.finetune(*self.DD['train'],batch_size=self.batch_size, gp_n_iter=100, verbose=0)
                X_test, y_test = self.DD['test']
                y_preds = self.reg.predict(X_test, return_var=True)
                yr = np.array(y_preds[0]).reshape((1,1))
                s = np.array(y_preds[1]).reshape((1,1))
                self.y_pred = self.reY(np.array(yr))[0,0]
                self.sigma = self.reY(np.array(s))[0,0]
            except: 
                print(self.dn)
                traceback.print_exc()
            pass
        else: pass
        print(self.y_obs,self.y_pred,self.sigma)
#        store_prediction_to_file(self.fname,self.dn,self.y_obs,self.y_pred,self.pr,self.prt,self.model)
        store_deepgp_prediction_to_file(self.fname,self.dn,self.y_obs,self.y_pred,self.sigma,self.pr,self.prt,self.model)
        return

def run_deepgp_model_per_date(details):
    y = details[0]
    reg = details[1]
    look_back = reg[1]
    clf = details[2]
    dn = details[3]
    data = details[4]
    alt_win = details[5]
    th = DeepGPPerDataPoint(y,reg,clf,dn,data,alt_win,look_back)
    th.run()
    return

def run_model_based_on_deepgp(Y, model="deepGP", trw=27, i=0):
    print("--> Loading data...")
    #_o, _xparams, _yparam = db.load_data_for_deterministic_reg()
    _o, _xparams, _yparam = db.load_data_with_goes_for_deterministic_reg()
    f_clf = "out/rf.pkl"
    clf = util.get_best_determinsistic_classifier(f_clf)
    print trw
    reg = (14,1,trw)
    N = 8*30*2
    #N = 1
    #_dates = [dt.datetime(Y,7,1) + dt.timedelta(hours=i*3) for i in range(N)]
#    i = 6
    _dates = [dt.datetime(Y,7,1) + dt.timedelta(hours=i*3)]
    print("-->Process for year:%d"%Y)
    years = [Y] * len(_dates)
    regs = [reg] * len(_dates)
    clfs = [clf] * len(_dates)
    alt_wins = [36] * len(_dates)
    data_array = [(_o, _xparams, _yparam)] * len(_dates)
    _a = []
    for x,y,z,dn,k,aw in zip(years, regs, clfs, _dates, data_array, alt_wins): _a.append((x,y,z,dn,k,aw))
    date_pool = Pool(1)
    date_pool.map(run_deepgp_model_per_date, _a)
    return


