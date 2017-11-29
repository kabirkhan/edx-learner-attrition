from collections import Counter
import numpy as np
import pandas as pd
import keras
from keras.models import Sequential, load_model
from keras.layers import Dense, Dropout
from keras.wrappers.scikit_learn import KerasClassifier
from sklearn import metrics
from sklearn.preprocessing import MinMaxScaler
from pipeline.util import *

# Function to create model, required for KerasClassifier
def create_model(optimizer='adam', num_hidden_layers=2, hidden_layers_dim=8):
    # create model
    model = Sequential()
    model.add(Dense(hidden_layers_dim, input_dim=9, activation='relu'))
    for i in range(num_hidden_layers):
        model.add(Dense(hidden_layers_dim, activation='relu'))
        model.add(Dropout(0.2))
    model.add(Dense(2, activation='softmax'))
    # Compile model
    model.compile(loss='categorical_crossentropy', optimizer=optimizer, metrics=['accuracy'])
    return model


def get_data(past_course_ids, current_course_id):
    train = None
    for course_id in past_course_ids:
        course_run_data = pd.read_csv('{}/{}/model_data.csv'.format(get_data_path(), course_id))
        if train is None:
            train = course_run_data
        else:
            train.append(course_run_data)

    print('Training data done.')

    train = train.reset_index(drop=True)
    test = pd.read_csv('{}/{}/model_data.csv'.format(get_data_path(), current_course_id))

    X_cols = [
        'course_week', 'num_video_plays', 'num_problems_attempted',
        'num_problems_correct', 'num_subsections_viewed', 'num_forum_posts',
        'num_forum_votes', 'avg_forum_sentiment', 'user_started_week',
    ]

    X_train = np.array(train[X_cols]).astype(np.float32)
    X_test = np.array(test[X_cols]).astype(np.float32)

    y_train = np.array(train['user_dropped_out_next_week']).astype(np.float32)
    y_test = np.array(test['user_dropped_out_next_week']).astype(np.float32)

    scaler = MinMaxScaler(feature_range=(0,1))
    scaler.fit(X_train)

    X_train = scaler.transform(X_train)
    X_test = scaler.transform(X_test)

    return (X_train, y_train, X_test, y_test)


def fit_score_predict(course_id, from_checkpoint=False):

    # TODO Fix how this training data is sampled
    # e.g. bootstrap sampling of a random number of courses
    # to get a total of > 1 million training samples
    past_course_ids = []
    for i in range(3):
        past_course_ids.append('Microsoft+DAT206x+{}T2017'.format(i + 1))

    print('GETTING DATA: ', past_course_ids)
    X_train, y_train, X_test, y_test = get_data(past_course_ids, course_id)
    print('Done.')

    # One hot encode labels
    y_train = keras.utils.to_categorical(y_train, num_classes=2)
    y_test = keras.utils.to_categorical(y_test, num_classes=2)
    batch_size = 20

    if from_checkpoint:
        model = load_model('model.h5')
    else:
        model = create_model()

        print('Fitting model')
        model.fit(X_train, y_train, epochs=10, batch_size=batch_size)
        print('Done')
        try:
            model.save('model.h5')
        except:
            print('FAILED TO SAVE MODEL')

    print('Evaluating model on data for course: {}'.format(course_id))

    score = model.evaluate(X_test, y_test, batch_size)
    preds = model.predict(X_test, batch_size)
    print('Accuracy: ', score)
    print(preds)

    # HEAVILY penalize false negatives due to the data imbalance of 0 classes
    y_labels = y_test.argmax(axis=1)
    softmax_threshold = Counter(y_labels)[1] / (Counter(y_labels)[1] + Counter(y_labels)[0])

    final_preds = []
    for pred in preds:
        if pred[1] > softmax_threshold:
            final_preds.append(1)
        else:
            final_preds.append(0)

    conf_matrix = metrics.confusion_matrix(y_test.argmax(axis=1), final_preds)

    print('FINAL RESULTS: ')
    print(conf_matrix, conf_matrix / len(y_test))
    print('Accuracy: ', score)

    return (final_preds, score, conf_matrix)
