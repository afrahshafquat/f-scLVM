"""
run inference on tody data
"""
import sys
import os
import ast
sys.path.append('./..')
import scipy as SP
import pdb
import cPickle as pickle
import core.sparseFAknown as sparseFA
import matplotlib as mpl
import matplotlib.lines as mlines
mpl.use('Agg')
import pylab as plt
import h5py
import brewer2mpl
from sklearn.decomposition import PCA
from sklearn.decomposition import RandomizedPCA
import rpy2.robjects.numpy2ri
rpy2.robjects.numpy2ri.activate()
from rpy2.robjects.packages import importr
from rpy2.robjects.vectors import FloatVector, StrVector
import rpy2.robjects as robjects
stats = importr('stats')
from rpy2.robjects.lib import ggplot2
grdevices = importr('grDevices')
cowplot = importr('cowplot')
gg2 = importr('ggplot2')



def mad(X):
    median = SP.median(X, axis=0)
    return SP.median(abs(X-median), axis=0)
    
def plotFac(FA, idx1, idx2, lab=None, terms=None, cols=None, isCont=False):
    X1 = FA.S.E1[:,idx1]
    X2 = FA.S.E1[:,idx2]
    if isCont==False:
        uLab = SP.unique(lab)  
        if cols==None:
             bmap=brewer2mpl.get_map('Paired', 'Qualitative', len(uLab))
             cols = bmap.hex_colors         
        pList=list()
        for i in range(len(X1)):
            pList.append(plt.plot(X1[i], X2[i], '.',color=cols[SP.where(lab[i]==uLab)[0]]))
        plt.xlabel(terms[idx1])
        plt.ylabel(terms[idx2])
        lList=list()
        for i in range(len(uLab)):
            lList.append( mlines.Line2D([], [], color=cols[i], marker='.',
                              markersize=7, label=uLab[i], linewidth=0))     
        plt.legend(handles=lList)
    else:
        plt.scatter(X1, X2, c=lab, s=20)
        plt.xlabel(terms[idx1])
        plt.ylabel(terms[idx2])        
    #plt.savefig('./Tcells_scatter.pdf')
    
def vcorrcoef(X,y):
    Xm = SP.reshape(SP.mean(X,axis=1),(X.shape[0],1))
    ym = SP.mean(y)
    r_num = SP.sum((X-Xm)*(y-ym),axis=1)
    r_den = SP.sqrt(SP.sum((X-Xm)**2,axis=1)*SP.sum((y-ym)**2))
    r = r_num/r_den
    return r
        
data_dir = '../../data/'
out_base = './results/'


if __name__ == '__main__':

    if 'cluster' in sys.argv:
        dFile = sys.argv[2]
        anno = sys.argv[3]
        nIterations = int(sys.argv[4])
        nHidden = int(sys.argv[5])
        idx_known = ast.literal_eval(sys.argv[6])
        doFast=bool(int(sys.argv[7]))
        if len(sys.argv)>7:
            idxCol = ast.literal_eval(sys.argv[8])
        else:
            idxCol=None
    else:
        
        dFile = 'Buettneretal_sfERCC.hdf5'
        anno = 'MSigDB2'
        nHidden = 3
        idx_known = []
        nIterations = 1000
        idxCol=[0,1]
        doFast=True


 
            
    minGenes = 15
    dataFile = h5py.File(os.path.join(data_dir, dFile), 'r')
    if anno=='REACTOME':
        terms = dataFile['termsR'][:]  
        pi = dataFile['PiR20'][:].T
    else:
        terms = dataFile['terms'][:]#[50:]
        pi = dataFile['Pi'][:].T#[:,50:]
        
    pi[pi>.5] =0.99
    pi[pi<.5] =1e-8   
    Y = dataFile['Yhet'][:].T
    if dFile=='Tcell.hdf5':
        Y = SP.log10(dataFile['Yhet'][:].T+1)
    elif dFile=='zeisel_microgliaR.hdf5':
        Y = SP.log2(dataFile['Yhet'][:].T+1)
    
    
    terms = terms[SP.sum(pi>.5,0)>minGenes]
    pi = pi[:,SP.sum(pi>.5,0)>minGenes]
    
    if doFast==True:
        idx_genes  = SP.logical_and(SP.sum(pi>.5,1)>0, Y.mean(0)>0.)#SP.any(pi>.5,1)
        Y = Y[:,idx_genes]
        pi = pi[idx_genes,:]
    
     
    terms = SP.hstack([SP.repeat('hidden',nHidden), terms])
    pi = SP.hstack([SP.ones((Y.shape[1],nHidden))*.99,pi])

    init_factors = {}
    
    isBias=0
    if len(idx_known)>0:
        known_names = dataFile['known_names'][:][idx_known]
        if len(dataFile['Known'][:].shape)>1:
            known = dataFile['Known'][:].T[:,idx_known]
        else:
            known = dataFile['Known'][:][:,SP.newaxis]
        known -= known.mean(0)
        known /= known.std(0)
        terms = SP.hstack([ known_names,terms])
        pi = SP.hstack([SP.ones((Y.shape[1],len(idx_known)))*.5,pi])
        init_factors['Known'] = known      
        if isBias==1:
            terms = SP.hstack([ 'bias',terms])
            pi = SP.hstack([SP.ones((Y.shape[1],1))*(1.-1e-10),pi])
            init_factors['Known'] =SP.hstack([SP.ones((Y.shape[0],1)), known])        
        
    else:
        known_names = '0'
        if isBias==1:
            terms = SP.hstack([ 'bias',terms])
            pi = SP.hstack([SP.ones((Y.shape[1],1))*(1.-1e-10),pi])
            init_factors['Known'] =SP.ones((Y.shape[0],1)) 
        #known_names = 'bias'
            
    if doFast==False:      
        out_dir = os.path.join(out_base,  dFile.split('.')[0],anno)
    else:
        out_dir = os.path.join(out_base,  dFile.split('.')[0],anno+'_fast')
                
    if not os.path.exists(out_dir):
        os.makedirs(out_dir)
        
    out_file = 'resHidden'+str(nHidden)+'99_Bias'+str(isBias)+'_Known__'+'__'.join(known_names)+'_Sort1e52k.hdf5'
    out_name = os.path.join(out_dir, out_file)
    print out_name  

    
    init_factors['iLatent'] = SP.where(terms=='hidden')[0]

    

    Y-=SP.mean(Y,0)

      
    K = pi.shape[1]

    #data for sparseFA instance
    


    init={'init_data':sparseFA.CGauss(Y),'Pi':pi,'init_factors':init_factors}
    sigmaOff = 1E-3
    sparsity = 'VB'

    #permutation move
    permutation_move = False
    #prior on noise level 
    priors = {'Eps': {'priors':[1E-3,1E-3]}}
    #how to initialize network?
    initType = 'pcaRand'
    terms0=terms
    pi0=pi
    FA0 = sparseFA.CSparseFA(components=K,sigmaOff=sigmaOff,sigmaOn=SP.ones(pi.shape[1])*1.0,sparsity=sparsity,nIterations=nIterations,permutation_move=permutation_move,priors=priors,initType=initType)
    FA0.init(**init)

                        
        
    pca = PCA(n_components=1)
    pca.fit(FA0.Z.E1)
    X = pca.transform(FA0.Z.E1)
    nFix = FA0.nKnown+FA0.nLatent
    
    
    IonPi = pi>.5
    varExpl = SP.zeros((K-nFix))
    for k in range(K-nFix):   
        pca = RandomizedPCA()
        Xpc = pca.fit_transform(Y[:,IonPi[:,k+nFix]])[:,0:1]                 
        varExpl[k] = pca.explained_variance_ratio_[0]    
    
    
    MPC = abs(vcorrcoef(FA0.initS[:,SP.argsort(FA0.W.Ilabel)].T,X.T))[nFix:]
    Ipi = SP.argsort(-MPC.ravel())
    IpiRev = SP.argsort(MPC.ravel())
    #Ipi = SP.argsort(varExpl.ravel())
    #IpiRev = SP.argsort(-varExpl.ravel())


    mRange = range(FA0.components)
    mRange[nFix:] = Ipi+nFix
    mRangeRev = range(FA0.components)
    mRangeRev[nFix:] = IpiRev+nFix
        
    pi = pi0[:,mRange]
    terms = terms0[mRange]     
    init={'init_data':sparseFA.CGauss(Y),'Pi':pi,'init_factors':init_factors}
    FA = sparseFA.CSparseFA(components=K,sigmaOff=sigmaOff,sigmaOn=SP.ones(pi.shape[1])*1.0,sparsity=sparsity,nIterations=nIterations,permutation_move=permutation_move,priors=priors,initType=initType)            
    FA.shuffle=True
    FA.init(**init) 
    for j in range(50):
        FA.update()      
        
    FANorev = FA   
  
    rel_contrib = SP.zeros(K)
    
    Ion = FA.W.C[:,:,1]>.5
    NonInf = SP.sum(FA.W.C[:,:,0]>.5,0)
    IonInf = FA.W.C[:,:,0]>.5
    for k in range(K):
        rel_contrib[k] = NonInf[k]/(FA.Alpha.E1[k]*(Y[:,IonInf[:,k]].var(0)-1./FA.Eps.E1[IonInf[:,k]]).sum()) 
    MAD = mad(FA.S.E1)
        
    pi = pi0[:,mRangeRev]
    terms = terms0[mRangeRev]
    init={'init_data':sparseFA.CGauss(Y),'Pi':pi,'init_factors':init_factors}        
    FArev = sparseFA.CSparseFA(components=K,sigmaOff=sigmaOff,sigmaOn=SP.ones(pi.shape[1])*1.0,sparsity=sparsity,nIterations=nIterations,permutation_move=permutation_move,priors=priors,initType=initType)            
    FArev.shuffle=True
    FArev.init(**init) 
    #FArev.iterate(forceIterations=True, nIterations=nIterations)
    for j in range(50):
        FArev.update() 
    
    print terms0[FArev.Alpha.E1[SP.argsort(mRangeRev)].argsort()]
        
    Ion = FArev.W.C[:,:,1]>.5
    NonInf = SP.sum(FArev.W.C[:,:,0]>.5,0)
    IonInf = FArev.W.C[:,:,0]>.5    
    rel_contribRev = SP.zeros(K)
    for k in range(K):
        rel_contribRev[k] = NonInf[k]/(FArev.Alpha.E1[k]*(Y[:,IonInf[:,k]].var(0)-1./FArev.Eps.E1[IonInf[:,k]]).sum()) 

    MADrev = mad(FArev.S.E1)
    
    
    IpiM = (0.5*FArev.Alpha.E1[SP.argsort(mRangeRev)][nFix:]+.5*FA.Alpha.E1[SP.argsort(mRange)][nFix:]).argsort()    
    Ilabel = SP.hstack([SP.arange(nFix),IpiM+nFix])
    
    IlabelRev = SP.hstack([SP.arange(nFix),FArev.Alpha.E1[SP.argsort(mRangeRev)][nFix:].argsort()+nFix])
 
    IpiMad = (0.5*FArev.Alpha.E1[SP.argsort(mRangeRev)][nFix:]*1/(MADrev[SP.argsort(mRangeRev)][nFix:])+.5*FA.Alpha.E1[SP.argsort(mRange)][nFix:]*(1/MAD[SP.argsort(mRange)][nFix:])).argsort()    
    IlabelMad = SP.hstack([SP.arange(nFix),IpiMad+nFix])
    
    IpiRel = SP.argsort(-(0.5*rel_contribRev[SP.argsort(mRangeRev)][nFix:]+.5*rel_contrib[SP.argsort(mRange)][nFix:]))    
    IlabelRel = SP.hstack([SP.arange(nFix),IpiRel+nFix])
    print terms0[Ilabel]

    
    #Ilabel = mRangeRev
    pi = pi0[:,Ilabel]
    pi[pi<.1] =1e-3
    terms = terms0[Ilabel] 
    init={'init_data':sparseFA.CGauss(Y),'Pi':pi,'init_factors':init_factors}
    FA = sparseFA.CSparseFA(components=K,sigmaOff=sigmaOff,sigmaOn=SP.ones(pi.shape[1])*1.0,sparsity=sparsity,nIterations=nIterations,permutation_move=permutation_move,priors=priors,initType=initType)            
    FA.shuffle=True
    FA.init(**init) 
    FA.iterate(forceIterations=True, nIterations=nIterations)
    FA.calcBound()
    
    Ion = FA.W.C[:,:,1]>.5
    NonInf = SP.sum(FA.W.C[:,:,0]>.5,0)
    IonInf = FA.W.C[:,:,0]>.5
    rel_contrib = SP.zeros(K)
    for k in range(K):
        rel_contrib[k] = NonInf[k]/(FA.Alpha.E1[k]*(Y[:,IonInf[:,k]].var(0)-1./FA.Eps.E1[IonInf[:,k]]).sum())      

    
    MAD = mad(FA.S.E1)
    alpha0 = (MAD>.1)*(rel_contrib)
    alpha = (MAD)*(rel_contrib)
    alpha2 = 1./(FA.Alpha.E1)
    alpha02 = (MAD>.5)*(1/(FA.Alpha.E1))

    print alpha02
    print SP.vstack([pi.sum(0)[FA.W.Ilabel][SP.argsort(alpha)],FA.W.C[:,:,0].sum(0)[SP.argsort(alpha)]])
    
        
    idxF = SP.argsort(-alpha)#[0:10]
    idxF0 = SP.argsort(-alpha0)#[0:10]
    idxF2 = SP.argsort(-alpha2)#[0:10]
    idxF02 = SP.argsort(-alpha02)#[0:10]
 
    plt_idx1 = 0
    plt_idx2 = 1
 
    #plot 
    dataf = robjects.DataFrame({'alpha': FloatVector(alpha02),'terms':terms})
    if type(idxCol) == list and len(idxCol)==1: idxCol=idxCol[0]
        
    if SP.isscalar(idxCol):        
        cc = dataFile['Known'][:].T[:,idxCol]
        datafs = robjects.DataFrame({'col': FloatVector(cc), 'X1': FloatVector(FA.S.E1[:,idxF02[plt_idx1]]), 
                            'X2': FloatVector(FA.S.E1[:,idxF02[plt_idx2]])}) 
        colName = dataFile['known_names'][:][idxCol]
    elif type(idxCol) == list and len(idxCol)==2:
        cc = dataFile['Known'][:].T[:,idxCol[0]]+2*dataFile['Known'][:].T[:,idxCol[1]] 
        S2 = FA.S.E1[:,idxF02[plt_idx2]]
        S1 = FA.S.E1[:,idxF02[plt_idx1]]
        datafs = robjects.DataFrame({'col': StrVector.factor(StrVector(cc)),
                                     'X1': FloatVector(S1), 'X2': FloatVector(S2)})
        colName = "Cell Cycle"
    elif type(idxCol) == list and len(idxCol)>2:       
        cc = dataFile['Known'][:].T[:,idxCol[0]]
        for i in range(len(idxCol)):        
            cc = cc+(i+1)*dataFile['Known'][:].T[:,idxCol[i]] 
        S2 = FA.S.E1[:,idxF02[plt_idx2]]
        S1 = FA.S.E1[:,idxF02[plt_idx1]]
        datafs = robjects.DataFrame({'col': StrVector.factor(StrVector(cc)),
                                     'X1': FloatVector(S1), 'X2': FloatVector(S2)})
        colName = "Cell Type"
    else: 
        S2 = FA.S.E1[:,idxF02[plt_idx2]]
        S1 = FA.S.E1[:,idxF02[plt_idx1]]
        datafs = robjects.DataFrame({'X1': FloatVector(S1), 'X2': FloatVector(S2)})
        colName=None



    p = ggplot2.ggplot(dataf)+ggplot2.aes_string(x='terms', y='alpha')+ggplot2.geom_point()+ \
        ggplot2.theme(**{'axis.title.y': ggplot2.element_text(angle=90,size = gg2.rel(1.2)),
        'axis.title.x': ggplot2.element_text(size = gg2.rel(1.2)),
        'axis.text.x': ggplot2.element_text(size=6, angle=90)})+\
        ggplot2.labs(x="Processes", y='Relevance')#+ theme(axis.title.y = 'element_text(size = rel(1.2))')+theme(axis.title.x = element_text(size = rel(1.2)))  
    p.save(out_name+'_relevance.pdf', height=4, width=7)
       
    labels=str(tuple(['G1', 'S', 'G2M']))
    if colName=="Cell Cycle":
        pScatter = ggplot2.ggplot(datafs)+\
            ggplot2.aes_string(x='X1', y='X2', colour="factor(col, labels=c%s)" % labels) +ggplot2.geom_point()+\
            ggplot2.theme(**{'axis.title.y': ggplot2.element_text(angle=90,size = gg2.rel(.9)),
            'axis.title.x': ggplot2.element_text(size = gg2.rel(.9))})+\
            ggplot2.labs(x=terms[idxF02[plt_idx1]], y=terms[idxF02[plt_idx2]])+\
            ggplot2.scale_colour_manual(name=colName, values=StrVector(['#1b9e77', '#d95f02', '#7570b3']))        
    elif colName=="Cell Type":
        labels=str(tuple(dataFile['known_names'][:][idxCol]))
        pScatter = ggplot2.ggplot(datafs)+ggplot2.aes_string(x='X1', y='X2', colour="factor(col, labels=c%s)" % labels)+ggplot2.geom_point()+\
            ggplot2.theme(**{'axis.title.y': ggplot2.element_text(angle=90,size = gg2.rel(.8)),
            'axis.title.x': ggplot2.element_text(size = gg2.rel(.8)),
            'axis.text.x': ggplot2.element_text(size = gg2.rel(.9))})+\
            ggplot2.labs(x=terms[idxF02[plt_idx1]], y=terms[idxF02[plt_idx2]])+\
            ggplot2.scale_colour_discrete(name =colName)

    elif type(colName)!=None and colName!=None:
        pScatter = ggplot2.ggplot(datafs)+ggplot2.aes_string(x='X1', y='X2', colour='col')+ggplot2.geom_point(alpha=0.4)+\
            ggplot2.theme(**{'axis.title.y': ggplot2.element_text(angle=90,size = gg2.rel(.8)),
            'axis.title.x': ggplot2.element_text(size = gg2.rel(.8)),
            'axis.text.x': ggplot2.element_text(size = gg2.rel(.9))})+\
            ggplot2.labs(x=terms[idxF02[plt_idx1]], y=terms[idxF02[plt_idx2]])+\
            ggplot2.scale_colour_continuous(name =colName)
    else:
         pScatter = ggplot2.ggplot(datafs)+ggplot2.aes_string(x='X1', y='X2')+ggplot2.geom_point()+\
            ggplot2.theme(**{'axis.title.y': ggplot2.element_text(angle=90,size = gg2.rel(.8)),
            'axis.title.x': ggplot2.element_text(size = gg2.rel(.8)),
            'axis.text.x': ggplot2.element_text(size = gg2.rel(.9))})+\
            ggplot2.labs(x=terms[idxF02[plt_idx1]], y=terms[idxF02[plt_idx2]])      

    pScatter.save(out_name+'_'+terms[idxF02[plt_idx1]]+'_'+terms[idxF02[plt_idx2]]+'_scatter.pdf', height=4, width=7) 
    
    out_file = h5py.File(out_name+'.hdf5','w')    
    out_file['alphaRaw'] = FA.Alpha.E1
    out_file['alpha'] = alpha
    out_file['alpha2'] = alpha2
    out_file['alpha02'] = alpha02
    out_file['alpha0'] = alpha0    
    out_file['W'] = FA.W.E1
    out_file['Eps'] = FA.Eps.E1
    out_file['S'] = FA.S.E1        
    out_file['Gamma'] = FA.W.C[:,:,0]
    out_file['pi'] = pi
    out_file['terms'] = terms
    out_file.close()
    pickle.dump(FA, open(out_name+'_FA.pickle', 'w'))
    


  




