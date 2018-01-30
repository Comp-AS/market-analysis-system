# -*- coding: utf-8 -*-
###############################################################################
#                                                                             #
#   Market Analysis System                                                    #
#   https://www.mql5.com/ru/users/terentyev23                                 #
#                                                                             #
#   M A R K E T   A N A L Y S I S   S C R I P T   W I T H   K E R A S         #
#                                                                             #
#   Aleksey Terentyev                                                         #
#   terentew.aleksey@ya.ru                                                    #
#                                                                             #
###############################################################################

import math
import matplotlib.pyplot as plt
import numpy as np

import sys
sys.path.append('../')
from mas.include import get_parameters
from mas.data import create_timeseries_matrix, dataset_to_traintest
from mas.data import get_delta, get_deltas_from_ohlc
from mas.data import get_diff, get_sigmoid_to_zero
from mas.models import save_model, load_model

from keras.models import Sequential
from keras.layers import Dense, GRU, LSTM, Dropout, Activation
from keras.layers import BatchNormalization
from keras.layers import LeakyReLU, PReLU
from keras.optimizers import RMSprop, SGD
from keras.optimizers import Adam, Nadam, Adagrad, Adamax, Adadelta
from keras.callbacks import ReduceLROnPlateau
from keras import regularizers

from statsmodels.nonparametric.smoothers_lowess import lowess
from sklearn.metrics import mean_squared_error


#=============================================================================#
#       P R E P A R E   V A R I A B L E S                                     #
#=============================================================================#
# params[symb+period, arg1, arg2, ..]
# params = get_parameters()
params = ['EURUSD1440', '-train', 100, '-graph']
limit = 5000
batch_size = 128
fit_epoch = 100
fit_train_test = 0.75
ts_lookback = 3
recurent_1 = 64
recurent_2 = 64
run_type = 0
graph = False

idx = 0
for item in params:
    if idx > 0:
        if item == '-train':
            run_type = 0
        elif item == '-predict':
            run_type = 1
        elif item == '-graph':
            graph = True
        elif item == '-limit':
            pass
        elif int(item) > 0:
            if params[idx-1] == '-train':
                fit_epoch = int(item)
            elif params[idx-1] == '-limit':
                limit = int(item)
    idx += 1

np.random.seed(13)


# Main
path = 'C:/Users/Alexey/AppData/Roaming/MetaQuotes/Terminal/287469DEA9630EA94D0715D755974F1B/MQL4/Files/ML-Assistant/'
# Server
# path = 'C:/Users/Adminka/AppData/Roaming/MetaQuotes/Terminal/287469DEA9630EA94D0715D755974F1B/MQL4/Files/ML-Assistant/'
workfile = params[0]
file_x = path + workfile + '_x.csv'
file_y = path + workfile + '_y.csv'
file_xx = path + workfile + '_xx.csv'
file_yy = path + workfile + '_yy.csv'
prefix = 'deep_regr_md_'
model = None
data_x = np.array([])
data_y = np.array([])
train_x = np.array([])
train_y = np.array([])
test_x = np.array([])
test_y = np.array([])
history = None

# print('Backend:', backend())
print('Work file:', workfile)


#=============================================================================#
#       L O A D   D A T A                                                     #
#=============================================================================#
def prepare_data(data):
    delta_prices = get_deltas_from_ohlc(data, 7)
    derivative1 = get_diff(data[:, 7], 1)
    derivative2 = get_diff(data[:, 8], 1)
    derivative3 = get_diff(data[:, 9], 1)
    derivative4 = get_diff(data[:, 10], 1)
    sigmoid = get_sigmoid_to_zero(data[:, 10])
    _lowess = lowess(data[:, 10], range(data.shape[0]), return_sorted=False)

    delta_ema1 = get_delta(data, 4, 5)
    delta_ema2 = get_delta(data, 6, 7)

    return np.array([data[:, 0], data[:, 1], # time data
                     data[:, 2], data[:, 3], # time data
                     data[:, 4], data[:, 5], # time data
                     data[:, 6], # time data
                     data[:, 7], data[:, 8], # prices data
                     data[:, 9], data[:, 10], # prices data
                     delta_prices[:, 0], delta_prices[:, 1], delta_prices[:, 2],
                     delta_prices[:, 3], delta_prices[:, 4], delta_prices[:, 5],
                     derivative1, derivative2,
                     derivative3, derivative4,
                     sigmoid,
                     _lowess,
                     data[:, 11], data[:, 12], # ema data
                     data[:, 13], data[:, 14], # ema data
                     delta_ema1, delta_ema2,
                     data[:, 15], data[:, 16], # macd
                     data[:, 17], data[:, 18], # atr, cci
                     data[:, 19] # rsi
                    ]).swapaxes(0, 1)

if run_type == 0:
    print('\nLoading Data...')

    train_data = np.genfromtxt(file_x, delimiter=';')
    target_data = np.genfromtxt(file_y, delimiter=';')

    data_x = prepare_data(train_data)
    data_x, data_y = create_timeseries_matrix(data_x, target_data, ts_lookback)

    # batch_input_shape=(batch_size, timesteps, units)
    data_x = np.reshape(data_x, (data_x.shape[0], 1, data_x.shape[1]))

    # For training validation
    train_x, test_x = dataset_to_traintest(data_x, ratio=fit_train_test, limit=limit)
    train_y, test_y = dataset_to_traintest(data_y, ratio=fit_train_test, limit=limit)
    print('Train/Test :', len(train_y), '/', len(test_y))


#=============================================================================#
#       P R E P A R E   M O D E L                                             #
#=============================================================================#
if run_type == 0:
    print('\nCreating Model...')

    model = Sequential()
    model.add(BatchNormalization(batch_input_shape=(None, data_x.shape[1], data_x.shape[2])))
    model.add(GRU(recurent_1,
                  return_sequences=True,
                  activity_regularizer=regularizers.l2(0.01)
                 ))
    model.add(LeakyReLU())
    model.add(Dropout(0.5))
    model.add(GRU(recurent_2,
                  return_sequences=True,
                  activity_regularizer=regularizers.l2(0.01)
                 ))
    model.add(LeakyReLU())
    model.add(Dropout(0.4))
    model.add(GRU(recurent_2,
                  activity_regularizer=regularizers.l2(0.01)
                 ))
    model.add(LeakyReLU())
    model.add(Dropout(0.3))
    model.add(BatchNormalization())
    model.add(Dense(16))
    model.add(Dense(8))
    model.add(Dense(1))

    save_model(model, prefix + workfile + '.model')
elif run_type == 1:
    model = load_model(prefix + workfile + '.model')

opt = Nadam()
model.compile(loss='hinge', optimizer=opt, metrics=['acc'])


#=============================================================================#
#       T R A I N I N G                                                       #
#=============================================================================#
if run_type == 0:
    print('\nTraining...')

    reduce_lr = ReduceLROnPlateau(factor=0.9, patience=5, min_lr=0.000001, verbose=1)

    history = model.fit(train_x, train_y,
                        batch_size=batch_size,
                        epochs=fit_epoch,
                        callbacks=[reduce_lr],
                        validation_data=(test_x, test_y)
                       )

    model.save_weights(prefix + workfile + '.hdf5')

    # calculate root mean squared error
    train_predict = model.predict(train_x)
    test_predict = model.predict(test_x)
    train_score = math.sqrt(mean_squared_error(train_y, train_predict))
    print('Train Score: %.6f RMSE' % (train_score))
    test_score = math.sqrt(mean_squared_error(test_y, test_predict))
    print('Test Score: %.6f RMSE' % (test_score))


#=============================================================================#
#       P R E D I C T I N G                                                   #
#=============================================================================#
print('\nPredicting...')

data_xx = np.genfromtxt(file_xx, delimiter=';')
data_xx = prepare_data(data_xx)
data_xx, empty = create_timeseries_matrix(data_xx, look_back=ts_lookback)
data_xx = np.reshape(data_xx, (data_xx.shape[0], 1, data_xx.shape[1]))

if run_type == 1:
    model.load_weights(prefix + workfile + '.hdf5')

predicted_output = model.predict(data_xx, batch_size=batch_size)

data_yy = np.array([])
for i in range(ts_lookback-1):
    data_yy = np.append(data_yy, 0.0)

data_yy = np.append(data_yy, predicted_output)
np.savetxt(file_yy, data_yy, fmt='%.6f', delimiter=';')
print("Predict saved:\n", file_yy)


#=============================================================================#
#       P L O T                                                               #
#=============================================================================#
if graph:
    plt.plot(data_yy)
    plt.title('Saved predict')
    plt.ylabel('direction')
    plt.xlabel('bar')
    plt.legend(['prediction'])
    plt.show()

    plt.plot(predicted_output)
    plt.title('Predicted')
    plt.ylabel('direction')
    plt.xlabel('bar')
    plt.legend(['buy', 'sell'], loc='best')
    plt.show()

    if run_type == 0:
        plt.figure()
        plt.plot(history.history['loss'])
        plt.plot(history.history['val_loss'])
        plt.title('Model loss')
        plt.ylabel('loss')
        plt.xlabel('epoch')
        plt.legend(['train', 'test'], loc='best')
        plt.show()

        plt.figure()
        plt.plot(history.history['acc'])
        plt.plot(history.history['val_acc'])
        plt.title('Model accuracy')
        plt.ylabel('acc')
        plt.xlabel('epoch')
        plt.legend(['train', 'test'], loc='best')
        plt.show()