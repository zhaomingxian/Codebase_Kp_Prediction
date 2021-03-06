##
#
##

import os
import matplotlib
matplotlib.use("Agg")
matplotlib.rcParams['agg.path.chunksize'] = 10000
import datetime as dt
import numpy as np
import matplotlib.pyplot as plt
import pandas as pd
from scipy.interpolate import interp1d
import math
from scipy.stats import pearsonr
from sklearn.preprocessing import MinMaxScaler
from scipy.stats import norm

np.random.seed(7)
import database as db

from sklearn.dummy import DummyClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.naive_bayes import GaussianNB
from sklearn.svm import LinearSVC
from sklearn.tree import DecisionTreeClassifier, ExtraTreeClassifier
from sklearn.neighbors import KNeighborsClassifier, RadiusNeighborsClassifier, NearestCentroid
from sklearn.ensemble import AdaBoostClassifier, BaggingClassifier, ExtraTreesClassifier, GradientBoostingClassifier, RandomForestClassifier
from sklearn.discriminant_analysis import LinearDiscriminantAnalysis, QuadraticDiscriminantAnalysis
from sklearn.neural_network import MLPClassifier

from sklearn.model_selection import train_test_split
from sklearn.metrics import roc_curve, auc, confusion_matrix

from sklearn.dummy import DummyRegressor
from sklearn.linear_model import LinearRegression, ElasticNet, BayesianRidge
from sklearn.svm import LinearSVR
from sklearn.tree import DecisionTreeRegressor, ExtraTreeRegressor
from sklearn.neighbors import KNeighborsRegressor
from sklearn.ensemble import AdaBoostRegressor, BaggingRegressor, ExtraTreesRegressor, GradientBoostingRegressor, RandomForestRegressor

from sklearn.gaussian_process import GaussianProcessRegressor
from sklearn.gaussian_process.kernels import RBF, Matern, RationalQuadratic as RQ

from sklearn.externals import joblib
from spacepy import plot as splot
from imblearn.under_sampling import RandomUnderSampler
import verify
from verify import Contingency2x2

from keras.models import Sequential
from keras.layers import Dense,LSTM,Embedding,Dropout
from keras.models import load_model

plt.style.use('fivethirtyeight')
plt.style.use('seaborn-custom')

font = {"family": "serif", "color":  "darkred", "weight": "normal", "size": 12}
fontTx = {"family": "serif", "color":  "darkred", "weight": "normal", "size": 13}
fonttext = {"family": "serif", "color":  "darkblue", "weight": "normal", "size": 12}
fontL = {"family": "serif", "color":  "darkblue", "weight": "normal", "size": 8}
fontT = {"family": "serif", "color":  "darkblue", "weight": "normal", "size": 20}
fontTy = {"family": "serif", "color":  "darkblue", "weight": "normal", "size": 15}
fonttitle = {"family": "serif", "color":  "black", "weight": "normal", "size": 14}
fontsuptitle = {"family": "serif", "color":  "black", "weight": "bold", "size": 20}

def nan_helper(y):
    nans = np.isnan(y)
    x = lambda z: z.nonzero()[0]
    f = interp1d(x(~nans), y[~nans], kind="cubic")
    y[nans] = f(x(nans))
    return y

def smooth(x,window_len=51,window="hanning"):
    if x.ndim != 1: raise ValueError, "smooth only accepts 1 dimension arrays."
    if x.size < window_len: raise ValueError, "Input vector needs to be bigger than window size."
    if window_len<3: return x
    if not window in ["flat", "hanning", "hamming", "bartlett", "blackman"]: raise ValueError, "Window is on of 'flat', 'hanning', 'hamming', 'bartlett', 'blackman'"
    s = np.r_[x[window_len-1:0:-1],x,x[-2:-window_len-1:-1]]
    if window == "flat": w = numpy.ones(window_len,"d")
    else: w = eval("np."+window+"(window_len)")
    y = np.convolve(w/w.sum(),s,mode="valid")
    d = window_len - 1
    y = y[d/2:-d/2]
    return y

def get_classifiers():
    # basic classifires
    dc = DummyClassifier(random_state=0)
    lr = LogisticRegression()
    gnb = GaussianNB()
    svc = LinearSVC(C=1)
    C0 = {"name":"Basic","methods":[(dc, "Dummy"), (lr, "Logit"),(gnb, "Naive Bayes"), (svc, "SVC")]}
    
    # decission trees
    dec_tree = DecisionTreeClassifier(random_state=0)
    etc_tree = ExtraTreeClassifier(random_state=0)
    C1 = {"name":"Decision Tree","methods":[(dec_tree, "Decision Tree"),(etc_tree, "Extra Tree")]}
    
    # NN classifirer
    knn = KNeighborsClassifier(n_neighbors=25,weights="distance")
    rnn = RadiusNeighborsClassifier(radius=20.0,outlier_label=1)
    nc = NearestCentroid()
    C2 = {"name":"Nearest Neighbors","methods":[(knn, "KNN"),(rnn, "Radius NN"),(nc, "Nearest Centroid")]}
    
    
    # ensamble models
    ada = AdaBoostClassifier()
    bg = BaggingClassifier(n_estimators=50, max_features=3)
    etsc = ExtraTreesClassifier(n_estimators=50,criterion="entropy")
    gb = GradientBoostingClassifier(max_depth=5,random_state=0)
    rfc = RandomForestClassifier(n_estimators=100)
    C3 = {"name":"Ensemble","methods":[(ada, "Ada Boost"),(bg,"Bagging"),(etsc, "Extra Trees"),
        (gb, "Gradient Boosting"), (rfc, "Random Forest")]}

    # discriminant analysis & GPC
    lda = LinearDiscriminantAnalysis()
    qda = QuadraticDiscriminantAnalysis()
    C4 = {"name":"Discriminant Analysis","methods":[(lda, "LDA"),(qda, "QDA")]}
    
    # neural net
    nn = MLPClassifier(alpha=0.1,tol=1e-8)
    C5 = {"name":"Complex Architecture","methods":[(nn, "Neural Network")]}
    
    CLF = [C0,C1,C2,C3,C4,C5]
    return CLF

def get_roc_details(clf, X_test, y_test):
    if hasattr(clf, "predict_proba"): y_score = clf.predict_proba(X_test)[:, 1]
    else:
        prob_pos = clf.decision_function(X_test)
        y_score = (prob_pos - prob_pos.min()) / (prob_pos.max() - prob_pos.min())
        pass
    fpr, tpr, threshold = roc_curve(y_test, y_score)
    roc_auc = auc(fpr, tpr)
    return y_score, fpr, tpr, roc_auc

def plotlm(solmin,solmax):
    font = {"family": "serif", "color":  "darkblue", "weight": "normal", "size": 12}
    fig, axes = plt.subplots(nrows=1,ncols=2,figsize=(12,8),dpi=180)
    fig.subplots_adjust(wspace=0.2,hspace=0.2)
    import seaborn as sns; 
    sns.set(color_codes=True)
    solmin.columns = [r"$B_x$",r"$B_y$",r"$B_z$",r"$V_x$",r"$V_y$",r"$V_z$",r"$n$",r"$T$",r"$P_{dyn}$",r"$E$",r"$\beta$", r"$M_a$"]
    corr = solmin.corr()
    cmap = sns.diverging_palette(220, 10, as_cmap=True)
    sns.heatmap(corr, cmap=cmap, vmax=1., center=0,
            square=True, linewidths=.5, cbar_kws={"shrink": .5}, ax=axes[0])
    plt.yticks(rotation=0)
    solmax.columns = [r"$B_x$",r"$B_y$",r"$B_z$",r"$V_x$",r"$V_y$",r"$V_z$",r"$n$",r"$T$",r"$P_{dyn}$",r"$E$",r"$\beta$", r"$M_a$"]
    corr = solmax.corr()
    cmap = sns.diverging_palette(220, 10, as_cmap=True)
    sns.heatmap(corr, cmap=cmap, vmax=1., center=0,
            square=True, linewidths=.5, cbar_kws={"shrink": .5}, ax=axes[1])
    plt.yticks(rotation=0)
    axes[0].text(0.5, -0.15, '(a) Solar Minimum',
        verticalalignment='center', horizontalalignment='center',
        transform=axes[0].transAxes,
        color='blue', fontdict=font)  
    axes[1].text(0.5, -0.15, '(b) Solar Maximum',
        verticalalignment='center', horizontalalignment='center',
        transform=axes[1].transAxes,
        color='blue', fontdict=font)
 
    plt.savefig("figure/Correlation.png",bbox_inches="tight")
    return

def plot_gpr(d_fname, s_fname, smin_stime, smin_etime, smax_stime, smax_etime):
    d_fname = s_fname
    font = {"family": "serif", "color":  "darkblue", "weight": "normal", "size": 12}
    fig, axes = plt.subplots(nrows=2,ncols=1,figsize=(8,6))
    #fmt = matplotlib.dates.DateFormatter("%m-%d")
    fmt = matplotlib.dates.DateFormatter("%d %b\n%Y")
    fig.subplots_adjust(hspace=0.5)
    print d_fname,s_fname
    data = pd.read_csv(d_fname)
    stdd = pd.read_csv(s_fname)
    data.dn = pd.to_datetime(data.dn)
    smin = data[(data.dn >= smin_stime) & (data.dn < smin_etime)]
    smax = data[(data.dn >= smax_stime) & (data.dn < smax_etime)]
    stdd.dn = pd.to_datetime(stdd.dn)
    std_smin = stdd[(stdd.dn >= smin_stime) & (stdd.dn < smin_etime)]
    std_smax = stdd[(stdd.dn >= smax_stime) & (stdd.dn < smax_etime)]
    print len(std_smin),len(std_smax),len(smin),len(smax)
    
    _o = smin
    _o = _o.sort_values(by=["dn"])
    _o = _o[(_o.prob_clsf != -1.) & (_o.y_pred != -1.) & (_o.y_pred >= 0) & (_o.y_pred <= 9.)]
    _o = _o.drop_duplicates(subset=["dn"])
    _os = std_smin
    _os = _os.sort_values(by=["dn"])
    _os = _os[(_os.prob_clsf != -1.) & (_os.y_pred != -1.) & (_os.y_pred >= 0) & (_os.y_pred <= 9.)]
    _os = _os.drop_duplicates(subset=["dn"])
    print len(_o),len(_os)
    y_pred = np.array(_o.y_pred.tolist())
    y_obs = np.array(_o.y_obs.tolist())
    sigma = np.abs(np.array(_o.y_pred) - np.array(_os.lb))
    ax = axes[0]
    ax.xaxis.set_major_formatter(fmt)
    ax.plot(_o.dn,y_obs,"ro",markersize=2,label=r"$K_{P_{obs}}$",alpha=0.6)
    ax.plot(_o.dn,y_pred,"bo",markersize=1,label=r"$K_{P_{pred}}$")
    ax.fill(np.concatenate([_o.dn.tolist(), _o.dn.tolist()[::-1]]),
         np.concatenate([y_pred - 0.684 * sigma,
                        (y_pred + 0.684 * sigma)[::-1]]),
         alpha=.5, fc='b', ec='None', label='50% confidence interval')
    ax.fill(np.concatenate([_o.dn.tolist(), _o.dn.tolist()[::-1]]),
         np.concatenate([y_pred - 1.9600 * sigma,
                        (y_pred + 1.9600 * sigma)[::-1]]),
         alpha=.3, fc='b', ec='None', label='95% confidence interval')
    ax.set_ylabel(r"$K_{P_{pred}}$")
    ax.set_xlabel(r"Time $UT$")
    ax.legend(loc="upper left",fontsize=6)
    ax.set_xlim(dt.datetime(1995,7,1), dt.datetime(1995,8,28))
    #ax.tick_params(axis="both",which="major",labelsize="15")
    ax.set_xlim(smin_stime, smin_etime)
    ax.text(1.05,0.5,"(a)",horizontalalignment='center',verticalalignment='center', transform=ax.transAxes, rotation=90,fontdict=font)
    #ax.set_xlim(dt.datetime(1995,7,1), dt.datetime(1995,8,28))

    _o = smax
    _o = _o.sort_values(by=["dn"])
    _o = _o[(_o.prob_clsf != -1.) & (_o.y_pred != -1.) & (_o.y_pred >= 0) & (_o.y_pred <= 9.)]
    _o = _o.drop_duplicates(subset=["dn"])
    _os = std_smax
    _os = _os.sort_values(by=["dn"])
    _os = _os[(_os.prob_clsf != -1.) & (_os.y_pred != -1.) & (_os.y_pred >= 0) & (_os.y_pred <= 9.)]
    _os = _os.drop_duplicates(subset=["dn"])
    print len(_o),len(_os)
    y_pred = np.array(_o.y_pred.tolist())
    y_obs = np.array(_o.y_obs.tolist())
    sigma = np.abs(np.array(_o.y_pred) - np.array(_os.lb))
    ax = axes[1]
    ax.xaxis.set_major_formatter(fmt)
    ax.plot(_o.dn,y_obs,"ro",markersize=2,label=r"$K_{P_{obs}}$",alpha=0.6)
    ax.plot(_o.dn,y_pred,"bo",markersize=1,label=r"$K_{P_{pred}}$")
    ax.fill(np.concatenate([_o.dn.tolist(), _o.dn.tolist()[::-1]]),
         np.concatenate([y_pred - 0.684 * sigma,
                        (y_pred + 0.684 * sigma)[::-1]]),
         alpha=.5, fc='b', ec='None', label='50% confidence interval')
    ax.fill(np.concatenate([_o.dn.tolist(), _o.dn.tolist()[::-1]]),
         np.concatenate([y_pred - 1.9600 * sigma,
                        (y_pred + 1.9600 * sigma)[::-1]]),
         alpha=.3, fc='b', ec='None', label='95% confidence interval')
    ax.set_ylabel(r"$K_{P_{pred}}$")
    ax.set_xlabel(r"Time $UT$")
    ax.legend(loc="upper left",fontsize=6)
    ax.set_xlim(dt.datetime(2004,7,1), dt.datetime(2004,8,28))
    #ax.set_xlim(dt.datetime(2004,7,1), dt.datetime(2004,8,28))
    ax.text(1.05,0.5,"(b)",horizontalalignment='center',verticalalignment='center', transform=ax.transAxes, rotation=90,fontdict=font)
    #ax.tick_params(axis="both",which="major",labelsize="15")
    ax.set_xlim(smax_stime, smax_etime) 

    fig.savefig("figure/GPR.png",bbox_inches="tight") 
    return

def plot_deepgp():
    fname = "out/det.deepGP.pred.27.csv"
    print(fname)
    _o = pd.read_csv(fname)
    _o.dn = pd.to_datetime(_o.dn)
    _o = _o[(_o.prob_clsf != -1.) & (_o.y_pred != -1.) & (_o.y_pred >= 0) & (_o.y_pred <= 9.)]
    _o = _o[(_o.dn >= dt.datetime(2004,7,1)) & (_o.dn <= dt.datetime(2004,8,28))]
    _o = _o.drop_duplicates(subset=["dn"])
    y_pred = np.array(_o.y_pred.tolist())
    y_obs = np.array(_o.y_obs.tolist())
    sigma = 3 * np.abs(np.array(_o.y_pred) - np.array(_o.lb))
    fig, ax = plt.subplots(nrows=1,ncols=1,figsize=(6,4))
    fmt = matplotlib.dates.DateFormatter("%m-%d")
    fmt = matplotlib.dates.DateFormatter("%d %b\n%Y")
    ax.xaxis.set_major_formatter(fmt)
    ax.plot(_o.dn,y_obs,"ro",markersize=2,label=r"$K_{P_{obs}}$",alpha=0.6)
    ax.plot(_o.dn,y_pred,"bo",markersize=1,label=r"$K_{P_{pred}}$")
    ax.fill(np.concatenate([_o.dn.tolist(), _o.dn.tolist()[::-1]]),
            np.concatenate([y_pred - 0.684 * sigma,
                (y_pred + 0.684 * sigma)[::-1]]),
            alpha=.5, fc='b', ec='None', label='50% confidence interval')
    ax.fill(np.concatenate([_o.dn.tolist(), _o.dn.tolist()[::-1]]),
            np.concatenate([y_pred - 1.9600 * sigma,
                (y_pred + 1.9600 * sigma)[::-1]]),
            alpha=.3, fc='b', ec='None', label='95% confidence interval')
    ax.set_ylabel(r"$K_{P_{pred}}$")
    ax.set_xlabel(r"Time $UT$")
    ax.legend(loc="upper left",fontsize=6)
    #ax.tick_params(axis="both",which="major",labelsize="15")
    ax.set_xlim(dt.datetime(2004,7,1), dt.datetime(2004,8,28))
    fig.savefig("figure/lstmgp.png",bbox_inches="tight")
    return

def proba_storm():
    import matplotlib.gridspec as gridspec
    spec = gridspec.GridSpec(ncols=1, nrows=10)
    fname = "out/det.deepGP.pred.27.csv"
    matplotlib.rcParams['xtick.labelsize'] = 10 
    print(fname)
    _o = pd.read_csv(fname)
    _o.dn = pd.to_datetime(_o.dn)
    _o = _o[(_o.prob_clsf != -1.) & (_o.y_pred != -1.) & (_o.y_pred >= 0) & (_o.y_pred <= 9.)]
    _o = _o[(_o.dn >= dt.datetime(2004,7,22)) & (_o.dn <= dt.datetime(2004,7,28))]
    _o = _o.drop_duplicates(subset=["dn"])
    y_pred = np.array(_o.y_pred.tolist())
    y_obs = np.array(_o.y_obs.tolist())
    sigma = 3 * np.abs(np.array(_o.y_pred) - np.array(_o.lb))
    fig = plt.figure(figsize=(10,6))
    fig.subplots_adjust(hspace=0.5)
    #fig, ax = plt.subplots(nrows=1,ncols=1,figsize=(10,6))
    ax0 = fig.add_subplot(spec[0:2, 0])
    ax0.set_ylim(0,1.)
    ax0.set_yticks([0.3,.6,.9,1.2])
    ax0.set_xticks([])
    ax0.set_xticklabels([])
    ax0.set_xlim(dt.datetime(2004,7,21,21), dt.datetime(2004,7,28,3))

    ax = fig.add_subplot(spec[2:, 0])
    fmt = matplotlib.dates.DateFormatter("%m-%d")
    fmt = matplotlib.dates.DateFormatter("%d %b\n%Y")
    ax.xaxis.set_major_formatter(fmt)
    ax.plot(_o.dn,y_obs,"ro",markersize=5,label=r"$K_{P_{obs}}$",alpha=0.6)
    ax.plot(_o.dn,y_pred,"bo",markersize=3,label=r"$K_{P_{pred}}$")
    ax.fill(np.concatenate([_o.dn.tolist(), _o.dn.tolist()[::-1]]),
         np.concatenate([y_pred - 1.9600 * sigma,
                        (y_pred + 1.9600 * sigma)[::-1]]),
         alpha=.4, fc='b', ec='None', label='95% confidence interval')
    ax.fill(np.concatenate([_o.dn.tolist(), _o.dn.tolist()[::-1]]),
         np.concatenate([y_pred - 0.684 * sigma,
                        (y_pred + 0.684 * sigma)[::-1]]),
         alpha=.7, fc='b', ec='None', label='50% confidence interval')
    ax.plot(_o.dn,4.5*np.ones(len(_o)),"k-.",markersize=3,label=r"$K_{P_{G_0}}$")
    ax.set_ylabel(r"$K_{P_{pred}}$")
    ax.set_xlabel(r"Time $UT$")
    #ax.legend(loc="upper left")
    ax.tick_params(axis="both",which="major",labelsize="15")
    ax.set_xlim(dt.datetime(2004,7,21,21), dt.datetime(2004,7,28,3))
    cmap = matplotlib.cm.get_cmap('Spectral')
    ax0.axhline(y=1.0,linewidth=0.8,color="k")
    ax0.set_ylabel("$Pr(e\geq G_1)$")
    for m,s,d in zip(y_pred, sigma,_o.dn.tolist()):
        pr = np.round((1 - norm.cdf(4.5, m, s))*100,1)
        c = "g"
        if pr > 30.: c = "orange"
        if pr > 60.: c = "red"
#        if pr > 30.: ax.text(d,12.5,str(pr)+"%",rotation=90)
        markerline, stemlines, baseline = ax0.stem([d], [pr/100.], c)
        ax0.plot([d],[pr/100.],c,marker="o",markersize=6)
        #plt.setp(stemlines, 'color', cmap(pr/100.))
        plt.setp(stemlines, 'linewidth', 3.5)
        pass
    ax.set_ylim(-2,15)
    fig.savefig("figure/strom.png",bbox_inches="tight")
    return


def kp_dist(df):
    n = 1./3.
    import seaborn as sns
    KpC = np.zeros((len(df)))
    U = df.Kp.unique()
    Kp = np.array(df.Kp)
    for u in U:
        if len(u) == 1: KpC[Kp==u] = float(u)
        else:
            if u[1] == "+": KpC[Kp==u] = float(U[0]) + n
            if u[1] == "-": KpC[Kp==u] = float(U[0]) - n
            pass
        pass   
    #splot.style("spacepy")
    fig = plt.figure(figsize=(7,4))
    ax = fig.add_subplot(111)
    ax.hist(KpC,density=False,alpha=0.7)
    ax.set_xticks([0,0+n,1-n,1,1+n,2-n,2,2+n,3-n,3,3+n,4-n,4,4+n,5-n,5,5+n,6-n,6,6+n,7-n,7,7+n,8-n,8,8+n,9-n,9])
    ax.set_xticklabels(["0  ",r"$0^+$",r"$1^-$","1  ",r"$1^+$",r"$2^-$","2  ",r"$2^+$",r"$3^-$","3  ",r"$3^+$",r"$4^-$","4  ",r"$4^+$",
                r"$5^-$","5  ",r"$5^+$",r"$6^-$","6  ",r"$6^+$",r"$7^-$","7  ",r"$7^+$",r"$8^-$","8  ",r"$8^+$",r"$9^-$","9  "], rotation=90)
    ax.set_yscale("log")
    ax.axvline(x=5-n,color="k")
    plt.xlabel(r"$K_p$")
    plt.ylabel(r"$f(K_p)$")
    plt.savefig("figure/Kp.png",bbox_inches="tight")
    return

def plot_deterministic_roc_curves(roc_eval_details, tag):
    fig, axes = plt.subplots(nrows=2,ncols=3,figsize=(12,8),dpi=180)
    fig.subplots_adjust(wspace=0.5,hspace=0.5)
    splot.style("spacepy")
    lw = 2
    I = 0
    for gname in roc_eval_details.keys():
        i,j = int(I/3), int(np.mod(I,3))
        ax = axes[i,j]
        clf_type = roc_eval_details[gname]
        for name in clf_type.keys():
            roc = roc_eval_details[gname][name]
            ax.plot(roc["fpr"], roc["tpr"], color=roc["c"], lw = lw, label="%s:AUC = %0.2f" % (name,roc["roc_auc"]))
            pass
        ax.plot([0, 1], [0, 1], color="navy", lw=lw, linestyle="--")
        ax.set_xlim([0.0, 1.0])
        ax.set_ylim([0.0, 1.0])
        ax.set_title(gname)
        ax.set_xlabel("False Positive Rate")
        ax.set_ylabel("True Positive Rate")
        ax.legend(loc="lower right",prop={"size": 8})
        I = I + 1
        pass
    fig.savefig("figure/ROC.png",bbox_inches="tight")
    return

def validate_model_matrices(clf, X_test, y_true):
    y_pred = clf.predict(X_test)
    CM = confusion_matrix(y_true, y_pred)
    C2x2 = Contingency2x2(CM.T)
    return C2x2


def get_regressor(name, trw=27):
    REGs = {}
    # basic regressor            
    REGs["dummy"] = (DummyRegressor(strategy="median"), name, trw)
    REGs["regression"] = (LinearRegression(), name, trw)
    REGs["elasticnet"] = (ElasticNet(alpha=.5,tol=1e-2), name, trw)
    REGs["bayesianridge"] = (BayesianRidge(n_iter=300, tol=1e-5, alpha_1=1e-06, alpha_2=1e-06, lambda_1=1e-06, lambda_2=1e-06, fit_intercept=True), name, trw)
    
    # decission trees
    REGs["dtree"] = (DecisionTreeRegressor(random_state=0,max_depth=5), name, trw)
    REGs["etree"] = (ExtraTreeRegressor(random_state=0,max_depth=5), name, trw)
    
    # NN regressor
    REGs["knn"] = (KNeighborsRegressor(n_neighbors=25,weights="distance"), name, trw)
    
    # ensamble models
    REGs["ada"] = (AdaBoostRegressor(), name, trw)
    REGs["bagging"] = (BaggingRegressor(n_estimators=50, max_features=3), name, trw)
    REGs["etrees"] = (ExtraTreesRegressor(n_estimators=50), name, trw)
    REGs["gboost"] = (GradientBoostingRegressor(max_depth=5,random_state=0), name, trw)
    REGs["randomforest"] = (RandomForestRegressor(n_estimators=100), name, trw)
    return REGs[name]

def get_hyp_param(kernel_type):
    hyp = {}
    if kernel_type == "RBF": hyp["l"] = 1.0
    if kernel_type == "RQ": 
        hyp["l"] = 1.0
        hyp["a"] = 0.1
    if kernel_type == "Matern": hyp["l"] = 1.0
    return hyp

def get_gpr(kernel_type, hyp, nrst = 10, trw=27):
    if kernel_type == "RBF": kernel = RBF(length_scale=hyp["l"],length_scale_bounds=(1e-02, 1e2))
    if kernel_type == "RQ": kernel = RQ(length_scale=hyp["l"],alpha=hyp["a"],length_scale_bounds=(1e-02, 1e2),alpha_bounds=(1e-2, 1e2))
    if kernel_type == "Matern": kernel = Matern(length_scale=hyp["l"],length_scale_bounds=(1e-02, 1e2), nu=1.4)
    gpr = GaussianProcessRegressor(kernel = kernel, n_restarts_optimizer = nrst)
    return (gpr, "GPR", trw)

def get_lstm(ishape,look_back=1, trw = 27):
    model = Sequential()
    model.add(LSTM(10, input_shape=(look_back, ishape)))
    model.add(Dropout(0.1))
    model.add(Dense(1))
    #model.add(Dense(1))
    model.compile(loss='mean_squared_error', optimizer='rmsprop')
    return (model, "LSTM", trw)

def get_lstm_classifier(ishape):
    model = Sequential()
    model.add(Embedding(input_dim = 188, output_dim = 50, input_length = ishape))
    model.add(LSTM(output_dim=256, activation='sigmoid', inner_activation='hard_sigmoid', return_sequences=True))
    model.add(Dropout(0.5))
    model.add(LSTM(output_dim=256, activation='sigmoid', inner_activation='hard_sigmoid'))
    model.add(Dropout(0.5))
    model.add(Dense(1, activation='sigmoid'))
    model.compile(loss='binary_crossentropy', optimizer='rmsprop',metrics=['accuracy'])
    return model

def run_validation(pred,obs,year,model):
    pred,obs = np.array(pred),np.array(obs)
    _eval_details = {}
    _eval_details["range"] = "N"
    if max(pred) > 9. or min(pred) < 0.: _eval_details["range"] = "Y"
    try: _eval_details["bias"] = np.round(verify.bias(pred,obs),2)
    except: _eval_details["bias"] = np.NaN
    try: _eval_details["meanPercentageError"] = np.round(verify.meanPercentageError(pred,obs),2)
    except: _eval_details["meanPercentageError"] = np.NaN
    try: _eval_details["medianLogAccuracy"] = np.round(verify.medianLogAccuracy(pred,obs),3)
    except: _eval_details["medianLogAccuracy"] = np.NaN
    try:_eval_details["symmetricSignedBias"] = np.round(verify.symmetricSignedBias(pred,obs),3)
    except: _eval_details["symmetricSignedBias"] = np.NaN
    try: _eval_details["meanSquaredError"] = np.round(verify.meanSquaredError(pred,obs),2)
    except: _eval_details["meanSquaredError"] = np.NaN
    try: _eval_details["RMSE"] = np.round(verify.RMSE(pred,obs),2)
    except: _eval_details["RMSE"] = np.NaN
    try: _eval_details["meanAbsError"] = np.round(verify.meanAbsError(pred,obs),2)
    except: _eval_details["meanAbsError"] = np.NaN
    try: _eval_details["medAbsError"] = np.round(verify.medAbsError(pred,obs),2)
    except: _eval_details["medAbsError"] = np.NaN
    
    try: _eval_details["nRMSE"] = np.round(verify.nRMSE(pred,obs),2)
    except: _eval_details["nRMSE"] = np.NaN
    try: _eval_details["forecastError"] = np.round(np.mean(verify.forecastError(pred,obs)),2)
    except: _eval_details["forecastError"] = np.NaN
    try: _eval_details["logAccuracy"] = np.round(np.mean(verify.logAccuracy(pred,obs)),2)
    except: _eval_details["logAccuracy"] = np.NaN
    
    try: _eval_details["medSymAccuracy"] = np.round(verify.medSymAccuracy(pred,obs),2)
    except: _eval_details["medSymAccuracy"] = np.NaN
    try: _eval_details["meanAPE"] = np.round(verify.meanAPE(pred,obs),2)
    except: _eval_details["meanAPE"] = np.NaN
    try: _eval_details["medAbsDev"] = np.round(verify.medAbsDev(pred),2)
    except: _eval_details["medAbsDev"] = np.NaN
    try: _eval_details["rSD"] = np.round(verify.rSD(pred),2)
    except: _eval_details["rSD"] = np.NaN
    try: _eval_details["rCV"] = np.round(verify.rCV(pred),2)
    except: _eval_details["rCV"] = np.NaN
    _eval_details["year"] = year
    _eval_details["model"] = model
    r,_ =  pearsonr(pred,obs)
    _eval_details["r"] = r
    return _eval_details


def load_lstm_clf(fname):
    model = load_model(fname)
    return model

def get_best_determinsistic_classifier(f_clf):
    if not os.path.exists(f_clf):
        # Dataset
        _xparams,X,y = db.load_data_for_deterministic_bin_clf()
        rus = RandomUnderSampler(return_indices=True)
        X_resampled, y_resampled, idx_resampled = rus.fit_sample(X, y)
        clf = RandomForestClassifier(n_estimators=100)
        clf.fit(X_resampled,y_resampled)
        joblib.dump(clf, f_clf)
    else:
        clf = joblib.load(f_clf)
    return clf

def get_stats(model, trw):
    fname = "out/det.%s.pred.%d.csv"%(model,trw)
    fname = "out/det.%s.pred.%d.g.csv"%(model,trw)
    print(fname)
    _o = pd.read_csv(fname)
    _o = _o[(_o.prob_clsf != -1.) & (_o.y_pred != -1.) & (_o.y_pred >= 0) & (_o.y_pred <= 9.)]
    y_pred = _o.y_pred.tolist()
    y_obs = _o.y_obs.tolist()
    _eval_details =  run_validation(y_pred,y_obs,"[1995-2016]",model)
    print _eval_details 
    splot.style("spacepy")
    fig, ax = plt.subplots(nrows=1,ncols=1,figsize=(6,6))
    ax.plot(y_pred,y_obs,"k.")
    print("Updated")
    strx = "RMSE=%.2f\nr=%.2f"%(_eval_details["RMSE"],_eval_details["r"])
    ax.text(0.2,0.95,strx,horizontalalignment='center',verticalalignment='center', transform=ax.transAxes)
    ax.set_xlabel(r"$K_{P_{pred}}$")
    ax.set_xlim(0,9)
    ax.set_ylim(0,9)
    ax.set_ylabel(r"$K_{P_{obs}}$")
    fig.savefig("out/stat/det.%s.pred.%d.png"%(model,trw))
    return


def run_for_TSS(model, trw):
    fdummy = "out/det.dummy.pred.%d.csv"%(trw)
    fname = "out/det.%s.pred.%d.csv"%(model,trw)
    _od = pd.read_csv(fdummy)
    _o = pd.read_csv(fname)
    _od = _od[(_od.prob_clsf != -1.) & (_od.y_pred != -1.) & (_od.y_pred >= 0) & (_od.y_pred <= 9.)]
    _o = _o[(_o.prob_clsf != -1.) & (_o.y_pred != -1.) & (_o.y_pred >= 0) & (_o.y_pred <= 9.)]
    _od.dn = pd.to_datetime(_od.dn)
    _o.dn = pd.to_datetime(_o.dn)

    stime = dt.datetime(1995,2,1)
    etime = dt.datetime(2016,9,20)
    d = stime
    skill = []
    t = []
    while(d < etime):
        try:
            t.append(d)
            dn = d + dt.timedelta(days=27)
            dum = _od[(_od.dn >= d) & (_od.dn < dn)]
            mod = _o[(_o.dn >= d) & (_o.dn < dn)]
            rmse_dum = verify.RMSE(dum.y_pred,dum.y_obs)
            rmse = verify.RMSE(mod.y_pred,mod.y_obs)
            print(d,rmse,rmse_dum,verify.skill(rmse, rmse_dum))
            skill.append(verify.skill(rmse, rmse_dum))
            d = d + dt.timedelta(days=1)
        except: pass
        pass
    skill = np.array(skill)
    #skill = nan_helper(skill)
    fmt = matplotlib.dates.DateFormatter("%d %b\n%Y")
    splot.style("spacepy")
    fig, ax = plt.subplots(nrows=1,ncols=1,figsize=(10,6))
    ax.xaxis.set_major_formatter(fmt)
    ax.plot(t,skill,"k.",label="")
    #ax.plot(t,smooth(np.array(skill),101),"r.")
    #strx = "RMSE:%.2f\nr:%.2f"%(_eval_details["RMSE"],_eval_details["r"])
    #ax.text(0.2,0.8,strx,horizontalalignment='center',verticalalignment='center', transform=ax.transAxes)
    ax.set_ylabel(r"$TSS(\%)$")
    ax.set_xlabel(r"$Time$")
    ax.set_xlim(dt.datetime(1995,1,1), dt.datetime(2017,1,1))
    ax.set_ylim(0,100)
    fig.savefig("out/stat/det.%s.tss.%d.png"%(model,trw)) 
    
def plot_pred(model,trw):
    fname = "out/det.%s.pred.%d.csv"%(model,trw)
    matplotlib.rcParams['xtick.labelsize'] = 10 
    print(fname)
    _o = pd.read_csv(fname)
    _o.dn = pd.to_datetime(_o.dn)
    _o = _o[(_o.prob_clsf != -1.) & (_o.y_pred != -1.) & (_o.y_pred >= 0) & (_o.y_pred <= 9.)]
    _o = _o[(_o.dn >= dt.datetime(2004,7,1)) & (_o.dn <= dt.datetime(2004,8,28))]
    _o = _o.drop_duplicates(subset=["dn"])
    y_pred = np.array(_o.y_pred.tolist())
    y_obs = np.array(_o.y_obs.tolist())
    sigma = 3 * np.abs(np.array(_o.y_pred) - np.array(_o.lb))
    splot.style("spacepy")
    fig, ax = plt.subplots(nrows=1,ncols=1,figsize=(10,6))
    fmt = matplotlib.dates.DateFormatter("%m-%d")
    ax.xaxis.set_major_formatter(fmt)
    ax.plot(_o.dn,y_obs,"ro",markersize=5,label=r"$K_{P_{obs}}$",alpha=0.6)
    ax.plot(_o.dn,y_pred,"bo",markersize=3,label=r"$K_{P_{pred}}$")
    ax.fill(np.concatenate([_o.dn.tolist(), _o.dn.tolist()[::-1]]),
         np.concatenate([y_pred - 1.9600 * sigma,
                        (y_pred + 1.9600 * sigma)[::-1]]),
         alpha=.4, fc='b', ec='None', label='95% confidence interval')
    ax.fill(np.concatenate([_o.dn.tolist(), _o.dn.tolist()[::-1]]),
         np.concatenate([y_pred - 0.684 * sigma,
                        (y_pred + 0.684 * sigma)[::-1]]),
         alpha=.7, fc='b', ec='None', label='50% confidence interval')
    ax.set_ylabel(r"$K_{P_{pred}}$")
    ax.set_xlabel(r"$UT$")
    ax.legend(loc="upper left")
    ax.tick_params(axis="both",which="major",labelsize="15")
    ax.set_xlim(dt.datetime(2004,7,1), dt.datetime(2004,8,28))
    fig.savefig("out/stat/det.pred.%s.%d.line.png"%(model,trw),bbox_inches="tight")
    return

#plot_pred("deepGP",27)


def proba_storm_forcast(model,trw):
    import matplotlib.gridspec as gridspec
    spec = gridspec.GridSpec(ncols=1, nrows=10)
    fname = "out/det.%s.pred.%d.csv"%(model,trw)
    matplotlib.rcParams['xtick.labelsize'] = 10 
    print(fname)
    _o = pd.read_csv(fname)
    _o.dn = pd.to_datetime(_o.dn)
    _o = _o[(_o.prob_clsf != -1.) & (_o.y_pred != -1.) & (_o.y_pred >= 0) & (_o.y_pred <= 9.)]
    _o = _o[(_o.dn >= dt.datetime(2004,7,22)) & (_o.dn <= dt.datetime(2004,7,28))]
    _o = _o.drop_duplicates(subset=["dn"])
    y_pred = np.array(_o.y_pred.tolist())
    y_obs = np.array(_o.y_obs.tolist())
    sigma = 3 * np.abs(np.array(_o.y_pred) - np.array(_o.lb))
    splot.style("spacepy")
    fig = plt.figure(figsize=(10,6))
    fig.subplots_adjust(hspace=0.5)
    #fig, ax = plt.subplots(nrows=1,ncols=1,figsize=(10,6))
    ax0 = fig.add_subplot(spec[0:2, 0])
    ax0.set_ylim(0,9)
    ax0.set_yticks([0,3,6,9])
    ax0.set_xticks([])
    ax0.set_xticklabels([])
    ax0.set_xlim(dt.datetime(2004,7,21,21), dt.datetime(2004,7,28,3))

    ax = fig.add_subplot(spec[2:, 0])
    fmt = matplotlib.dates.DateFormatter("%m-%d")
    ax.xaxis.set_major_formatter(fmt)
    ax.plot(_o.dn,y_obs,"ro",markersize=5,label=r"$K_{P_{obs}}$",alpha=0.6)
    ax.plot(_o.dn,y_pred,"bo",markersize=3,label=r"$K_{P_{pred}}$")
    ax.fill(np.concatenate([_o.dn.tolist(), _o.dn.tolist()[::-1]]),
         np.concatenate([y_pred - 1.9600 * sigma,
                        (y_pred + 1.9600 * sigma)[::-1]]),
         alpha=.4, fc='b', ec='None', label='95% confidence interval')
    ax.fill(np.concatenate([_o.dn.tolist(), _o.dn.tolist()[::-1]]),
         np.concatenate([y_pred - 0.684 * sigma,
                        (y_pred + 0.684 * sigma)[::-1]]),
         alpha=.7, fc='b', ec='None', label='50% confidence interval')
    ax.plot(_o.dn,4.5*np.ones(len(_o)),"k-.",markersize=3,label=r"$K_{P_{G_0}}$")
    ax.set_ylabel(r"$K_{P_{pred}}$")
    ax.set_xlabel(r"$UT$")
    #ax.legend(loc="upper left")
    ax.tick_params(axis="both",which="major",labelsize="15")
    ax.set_xlim(dt.datetime(2004,7,21,21), dt.datetime(2004,7,28,3))
    cmap = matplotlib.cm.get_cmap('Spectral')
    for m,s,d in zip(y_pred, sigma,_o.dn.tolist()):
        pr = np.round((1 - norm.cdf(4.5, m, s))*100,1)
        c = "g"
        if pr > 30.: c = "orange"
        if pr > 60.: c = "red"
        if pr > 30.: ax.text(d,12.5,str(pr)+"%",rotation=90)
        markerline, stemlines, baseline = ax0.stem([d], [m], c)
        ax0.plot([d],[m],c,marker="o",markersize=6)
        #plt.setp(stemlines, 'color', cmap(pr/100.))
        plt.setp(stemlines, 'linewidth', 3.5)
        pass
    ax.set_ylim(-2,15)
    fig.savefig("out/stat/det.pred.%s.%d.forecast.png"%(model,trw),bbox_inches="tight")
    return
#proba_storm_forcast("deepGP",27)
