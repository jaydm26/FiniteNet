# -*- coding: utf-8 -*-
"""
Created on Tue Sep 24 18:08:55 2019

"""
import torch
from torch import nn
from torch.nn.parameter import Parameter

import matplotlib.pyplot as plt
import numpy as np
import matplotlib as mpl
import time

from numpy import genfromtxt
from HelperFunctions import makeIC, resh, reshKS, wenoCoeff, exactSol, randGrid
plt.close('all') # close all open figures
# Define and set custom LaTeX style
styleNHN = {
        "pgf.rcfonts":False,
        "pgf.texsystem": "pdflatex",   
        "text.usetex": False,
        "font.family": "serif"
        }
mpl.rcParams.update(styleNHN)

# Plotting defaults
ALW = 0.75  # AxesLineWidth
FSZ = 12    # Fontsize
LW = 2      # LineWidth
MSZ = 5     # MarkerSize
SMALL_SIZE = 8    # Tiny font size
MEDIUM_SIZE = 10  # Small font size
BIGGER_SIZE = 14  # Large font size
plt.rc('font', size=FSZ)         # controls default text sizes
plt.rc('axes', titlesize=FSZ)    # fontsize of the axes title
plt.rc('axes', labelsize=FSZ)    # fontsize of the x and y labels
plt.rc('xtick', labelsize=FSZ)   # fontsize of the x-tick labels
plt.rc('ytick', labelsize=FSZ)   # fontsize of the y-tick labels
plt.rc('legend', fontsize=FSZ)   # legend fontsize
plt.rc('figure', titlesize=FSZ)  # fontsize of the figure title
plt.rcParams['axes.linewidth'] = ALW    # sets the default axes lindewidth to ``ALW''
plt.rcParams["mathtext.fontset"] = 'cm' # Computer Modern mathtext font (applies when ``usetex=False'')

# Define the network architecture
class Model(nn.Module):
    def __init__(self, input_size, output_size, hidden_dim, n_layers):
        super(Model, self).__init__()
        self.hidden_dim = hidden_dim
        self.n_layers = n_layers
        
        # RNN Layer
        self.lstm = nn.LSTM(input_size, hidden_dim, n_layers, batch_first=True).double()
        # Fully connected layer
        #self.fc1 = nn.Linear(hidden_dim, hidden_dim).double()
        self.fc2 = nn.Linear(hidden_dim, 5).double()
        self.trf = nn.Linear(5, 5).double()
        #cm = Parameter(torch.tensor([[0.8,-0.2,-0.2,-0.2,-0.2],[-0.2,0.8,-0.2,-0.2,-0.2],[-0.2,-0.2,0.8,-0.2,-0.2],[-0.2,-0.2,-0.2,0.8,-0.2],[-0.2,-0.2,-0.2,-0.2,0.8]]).double())#1st order
        cm = Parameter(torch.tensor([[0.4,-0.4,-0.2,0,0.2],[-0.4,0.7,-0.2,-0.1,0],[-0.2,-0.2,0.8,-0.2,-0.2],[0,-0.1,-0.2,0.7,-0.4],[0.2,0,-0.2,-0.4,0.4]]).double())#2nd order
        #cm = Parameter(torch.tensor([[4/35,-9/35,3/35,1/7,-3/35],[-9/35,22/35,-12/35,-6/35,1/7],[3/35,-12/35,18/35,-12/35,3/35],[1/7,-6/35,-12/35,22/35,-9/35],[-3/35,1/7,3/35,-9/35,4/35]]).double())#3rd order
        #cv = Parameter(torch.tensor([0.2,0.2,0.2,0.2,0.2]).double())#1st order
        cv = Parameter(torch.tensor([0.1,0.15,0.2,0.25,0.3]).double())#2nd order
        #cv = Parameter(torch.tensor([-17/105,59/210,97/210,8/21,4/105]).double())#3rd order
        self.trf.bias = cv
        self.trf.weight = cm
        
        for p in self.trf.parameters():
            p.requires_grad=False
    
    def forward(self, ui, dt, dx, hidden, test):
        Nx = ui.size(2)
        Nt = ui.size(1)
        uip = torch.zeros(Nx,Nt,5).double()

        uip = resh(ui)
        ci = wenoCoeff(uip)
        cm = torch.zeros_like(uip)
        cm[:,:,0] =  2/60
        cm[:,:,1] =-13/60
        cm[:,:,2] = 47/60
        cm[:,:,3] = 27/60
        cm[:,:,4] = -3/60
        if(test==1):
            f, hidden = self.lstm(uip, hidden)# Passing in the input and hidden state into the model and obtaining outputs
            #f = self.fc1(f)
            fi = self.fc2(f)
            f = fi + cm
            f = self.trf(f)#transform coefficients to be consistent
        else:
            f = ci.detach()
            fi = 0
        dui = torch.t(torch.sum(f*uip, dim = 2)).unsqueeze(0)
        u1 = ui - dt/dx*(dui**2-dui.roll(1,2)**2)/2
        
        u1p = resh(u1)
        c1 = wenoCoeff(u1p)
        if(test==1):
            f, hidden = self.lstm(u1p, hidden)# Passing in the input and hidden state into the model and obtaining outputs
            #f = self.fc1(f)
            f1 = self.fc2(f)
            f = f1 + cm
            f = self.trf(f)#transform coefficients to be consistent
        else:
            f = c1.detach()
            f1 = 0
        du1 = torch.t(torch.sum(f*u1p, dim = 2)).unsqueeze(0)
        u2 = 3/4*ui + 1/4*u1 - 1/4*dt/dx*(du1**2-du1.roll(1,2)**2)/2
               
        u2p = resh(u2)
        c2 = wenoCoeff(u2p)
        if(test==1):
            f, hidden = self.lstm(u2p, hidden)# Passing in the input and hidden state into the model and obtaining outputs
            #f = self.fc1(f)
            f2 = self.fc2(f)
            f = f2 + cm
            f = self.trf(f)#transform coefficients to be consistent
        else:
            f = c2.detach()
            f2 = 0
        du2 = torch.t(torch.sum(f*u2p, dim = 2)).unsqueeze(0)
        out = 1/3*ui + 2/3*u2 - 2/3*dt/dx*(du2**2-du2.roll(1,2)**2)/2
        return out, hidden, (fi**2+ f1**2+ f2**2)
    
    def init_hidden(self, batch_size):
        # This method generates the first hidden state of zeros which we'll use in the forward pass
        hidden = torch.zeros(self.n_layers, batch_size, self.hidden_dim,dtype=torch.double)
        cell = torch.zeros(self.n_layers, batch_size, self.hidden_dim,dtype=torch.double)
         # We'll send the tensor holding the hidden state to the device we specified earlier as well
        hc = (hidden,cell)
        return hc

# Instantiate the model with hyperparameters
model = Model(input_size=5, output_size=1, hidden_dim=32, n_layers=3)

# Define hyperparameters
lr = 0.001

# Define Loss, Optimizer
criterion = nn.MSELoss()
optimizer = torch.optim.Adam(model.parameters(), lr=lr)
n_epochs = 400

errs_WE = torch.zeros(n_epochs)
errs_NN = torch.zeros(n_epochs)
rel_err = torch.zeros(n_epochs)
def burgEx(xgf,tgf,IC):
    Nt = xgf.size()[1]-1
    solt = torch.zeros_like(torch.t(xgf))
    solt = solt.unsqueeze(0)
    solt[:,0,:] = IC
    x_t = IC
    x_t = x_t.unsqueeze(0)
    x_t = x_t.unsqueeze(0)
    for i in range(0,Nt):
        x_t, hidden1, p1 = model(x_t,dt,dx, 0, 0)
        solt[:,i+1,:] = x_t
    return solt[:,0::4,0::4]

errs_WE = torch.zeros(n_epochs)
errs_NN = torch.zeros(n_epochs)
L = 1
S = 100
cfl = 0.25
dx = 0.01
dt = cfl*dx
T = dt*(S)
xc = torch.linspace(0,L,int(L/dx)+1,dtype=torch.double)
xcf = torch.linspace(0,L,int(L/dx)*4+1,dtype=torch.double)
xc = xc[:-1]
xcf = xcf[:-1]
dxf = xcf[1] - xcf[0]
tc = torch.linspace(0,T,int(T/dt)+1,dtype=torch.double)
tcf = torch.linspace(0,T,int(T/dt)*4+1,dtype=torch.double)
dtf = tcf[1] - tcf[0]
xg,tg = torch.meshgrid(xc,tc)#make the coarse grid
xgf,tgf = torch.meshgrid(xcf,tcf)#make the fine grid

def compTV(u):
    dif = abs(u.roll(1)-u)
    return torch.sum(dif)
batch_size = xc.size(0)
IC_fx = makeIC(L)
mbs = 5

model.load_state_dict(torch.load('InvNet'))

n_tests = 1000
test_rat = torch.zeros(n_tests)
test_TV = torch.zeros(n_tests)
min_rat = 1

icf = makeIC(L)
for j in range(0,n_tests):
    IC = icf(xcf)
    IC = IC - min(IC)
    target_seq =  burgEx(xgf,tgf,IC)
    
    hidden1 = model.init_hidden(batch_size)
    h1_we = model.init_hidden(batch_size)

    x_t = target_seq[0,0,:]
    output = torch.zeros_like(target_seq)
    output_we = torch.zeros_like(target_seq)
    x_t = x_t.unsqueeze(0)
    x_t = x_t.unsqueeze(0)
    y_t = x_t[:,:,:]
    
    output[:,0,:] = x_t.detach()
    output_we[:,0,:] = x_t.detach()
    
    for i in range(0,S):
        x_t, hidden1, f1nn = model(x_t.detach(),dt,dx, hidden1, 1)
        y_t, h1_we, f1we = model(y_t.detach(),dt,dx, h1_we, 0)
        output[:,i+1,:] = x_t.detach()
        output_we[:,i+1,:] = y_t.detach()
    
    err_FNN = ((output-target_seq)**2).mean()
    err_WE5 = ((output_we-target_seq)**2).mean()
    test_rat[j] = (err_FNN/err_WE5).detach()
    test_TV[j] = compTV(target_seq[0,0,:]).detach()
    if(min_rat>=test_rat[j]):
        min_rat=test_rat[j].detach()
        sol_eg = target_seq.detach()
        sol_NN = output.detach()
        sol_WE = output_we.detach()
    print('Iter: ',j,' Err: ',test_rat[j])

#Plot total variation vs error ratio
plt.figure()
plt.plot(test_TV,test_rat,'.')
plt.xlabel('$TV(u(x,0))$')
plt.ylabel('Error Ratio')
plt.tight_layout()

#Animate a solution
plt.figure()
for i in range(0,len(tc)):
    plt.clf()
    plt.plot(xc,output[0,i,:].detach())
    plt.plot(xc,output_we[0,i,:].detach())
    plt.plot(xc,target_seq[0,i,:].detach())
    plt.pause(0.001)
plt.legend(('RNN','FDM','Exact'))

#Make histogram of error ratio
plt.figure(figsize=(6, 2))
heights,bins = np.histogram(torch.log10(test_rat).detach(),bins=20)
heights = heights/sum(heights)
plt.bar(bins[:-1],heights,width=(max(bins) - min(bins))/len(bins), color="blue", alpha=0.5)
plt.xlabel('Error Ratio')
plt.ylabel('Frequency')
plt.xticks((-0.8,-0.6,-0.4,-0.2,0,0.2),['$10^{-0.8}$','$10^{-0.6}$','$10^{-0.4}$','$10^{-0.2}$','$10^0$','$10^{0.2}$'])
plt.tight_layout()
