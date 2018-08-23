import matplotlib
matplotlib.use('Agg')
import numpy as np
from utils import *
from ConvNet import *
from sklearn import metrics
import torch 
import torchvision
import torchvision.transforms as transforms
import torch.utils.data as data
from os.path import exists
from os import makedirs, environ
from Bio import SeqIO  ## fasta read
import torch.nn.functional as F
import torch.nn as nn
import math
import torch.utils.model_zoo as model_zoo
import sys
sys.path.append(environ['VIENNA_PATH'])
import RNA
import matplotlib.pyplot as plt
from matplotlib.ticker import MaxNLocator
import timeit

## create directories for results and modelsgh
if not exists("./results/"):
  makedirs("./results/")

if not exists("./results/test"):
  makedirs("./results/test/")

if not exists("./weights/"):
  makedirs("./weights/")

if not exists("./weights/test"):
  makedirs("./weights/test/")

class DriveData(data.Dataset):
  def __init__(self, pos_filename, neg_filename, transform=None):
    self.transform = transform
    X_pos = import_seq(pos_filename)
    X_neg = import_seq(neg_filename)
    self.__xs = X_pos + X_neg
    self.__ys = [0] * len(X_pos) + [1] * len(X_neg)

  def __getitem__(self, index):
    return (encode(self.__xs[index], RNA.fold(self.__xs[index])[0], RNA.fold(self.__xs[index])[1]), self.__ys[index])

  def __len__(self):
    return len(self.__xs)

def update_lr(optimizer, lr):    
  for param_group in optimizer.param_groups:
    param_group['lr'] = lr

device = torch.device('cuda:0' if torch.cuda.is_available() else 'cpu')
N_EPOCH = 40
SPECIES = ['human', 'whole']
BATCH_SIZE = 64
NUM_CLASSES = 2
LEARNING_RATE = 0.01


for _species in SPECIES:
  WriteFile = open("./results/test/%s_test.rst" % _species ,"w")
  rst = []
  loss_list = []
  accuracy_list = []
  time = []
  model = ConvNet().to(device)
  model = model.double()
  weights = [4.0, 1.0]
  class_weights = torch.DoubleTensor(weights).to(device)
  criterion = nn.CrossEntropyLoss(weight=class_weights)
  optimizer = torch.optim.Adagrad(model.parameters(), lr=LEARNING_RATE, weight_decay=0.00001)
  train_dataset = DriveData("./dataset/cv/%s/%s_pos_all.fa" % (_species,_species),
    "./dataset/cv/%s/%s_neg_all.fa" % (_species,_species))
  test_dataset = DriveData("./dataset/test/%s/%s_pos_test.fa" % (_species,_species),
    "./dataset/test/%s/%s_neg_test.fa" % (_species,_species))
  train_loader = torch.utils.data.DataLoader(dataset=train_dataset, batch_size=BATCH_SIZE, num_workers=8, shuffle=True)
  test_loader = torch.utils.data.DataLoader(dataset=test_dataset, batch_size=BATCH_SIZE, num_workers=8, shuffle=False)
  curr_lr = LEARNING_RATE
  for epoch in range(N_EPOCH):
    start = timeit.default_timer()
    print(epoch)
    correct = 0
    total = 0
    loss_total = 0
    for i, (seqs, labels) in enumerate(train_loader):
      seqs = seqs.to(device)
      labels = labels.to(device)
      outputs = model(seqs)
      _, predicted = torch.max(outputs.data, 1)
      total += labels.size(0)
      correct += (predicted == labels).sum().item()
      loss = criterion(outputs, labels)
      optimizer.zero_grad()
      loss.backward()
      optimizer.step()
      loss_total += loss.item()
    stop = timeit.default_timer()
    time.append(stop - start)
    print(time)
    loss_list.append(loss_total)
    accuracy_list.append(float(correct) / total)
               
    _, ax1 = plt.subplots()
    ax2 = ax1.twinx()
    ax1.plot(loss_list)
    ax2.plot(accuracy_list, 'r')
    ax1.set_xlabel("epoch")
    ax1.set_ylabel("training loss")
    ax2.set_ylabel("training accuracy")
    ax1.set_title("training accuracy and loss")
    ax1.xaxis.set_major_locator(MaxNLocator(integer=True))
    plt.savefig("./results/test/accuracy_loss_%s.png" %_species, dpi=300)
    plt.close()

    # Test the model
    model.eval()
    with torch.no_grad():
      predictions = []
      Y_test = []
      for seqs, labels in test_loader:
        seqs = seqs.to(device)
        labels = labels.to(device)
        outputs = model(seqs)
        predictions.extend(outputs.data)
        Y_test.extend(labels)
      rst = perfeval(F.softmax(torch.stack(predictions), dim=1).cpu().numpy(), Y_test, verbose=1)
      wrtrst(WriteFile, rst, 0, epoch)
  print(time)    
  WriteFile.close()
  torch.save(model.state_dict(), "./weights/test/%s_test.pt" % _species)
  #model.load_state_dict(torch.load("./weights/test/%s_test.pt" % _species))
  model.eval()
  with torch.no_grad():
    predictions = []
    Y_test = []
    for seqs, labels in test_loader:
      seqs = seqs.to(device)
      labels = labels.to(device)
      outputs = model(seqs)
      predictions.extend(outputs.data)
      Y_test.extend(labels)
    predicted = F.softmax(torch.stack(predictions), dim=1).cpu().numpy()
    predicted_positive = []
    predicted_negative = []
    for i in range(len(Y_test)):
      predicted_positive.append(predicted[i][Y_test[i]])
      predicted_negative.append(predicted[i][1 - Y_test[i]])
    plt.figure()
    plt.hist(predicted_positive, normed=True, bins=100, histtype=u'step', color='black', label='Positive')
    plt.hist(predicted_negative, normed=True, bins=100, histtype=u'step', color='blue', label='Negative')
    plt.xlabel("Prediction")
    plt.ylabel("Frequency")
    plt.legend(loc="upper right")
    plt.savefig("./results/test/%s_test.png" % _species)