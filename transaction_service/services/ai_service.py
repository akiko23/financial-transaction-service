import pandas as pd
import numpy as np

def normalize_date(date: str):
    date = date.split('/')
    if date[1].startswith('0'):
        date[1] = date[1][1:]
    if len(date[2]) == 2:
        date[2] = '20' + date[2]
    return '/'.join(date)


def data_normalization(data):
    # Date   Balance  withraw   deposit   ...
    # d/m/Y

    data = data.dropna()
    data['Date'] = data['Date'].apply(normalize_date)
    data = data.set_index('Date')
    data.index = pd.to_datetime(data.index, format='%d/%m/%Y')
    data = data.dropna()

    data['day'] = data.index.day
    data['month'] = data.index.month
    data['weekofyear'] = data.index.isocalendar().week
    data['is_weekend'] = data.index.dayofweek.isin([5, 6])

    data['Transaction'] = data['Deposit'] - data['Withdrawal']
    data = data.drop(labels='Deposit', axis=1)
    data = data.drop(labels='Withdrawal', axis=1)

    data['is_deposit'] = data['Transaction'] > 0
    data['Transaction'] = data['Transaction'].abs()


    return data


def predict(model, data) -> str:

    # INPUT
    # Date   Date.1   Balance  Withraw   Deposit.
    # d/m/Y  d/m/Y

    # OUTPUT
    # [{'shoping': 0.999, 'food': 0.1, ... }, ... ]

    data = data_normalization(data)

    probabilities = model.predict_proba(data)
    indices = np.argmax(probabilities, axis=1)
    answer = model.classes_[indices]

    # answer = model.predict_proba(data)
    return answer[0]


def fit_model(model, data):
    # Date   Date.1   Balance  Withraw   Deposit   Category.
    # d/m/Y  d/m/Y
    data = data_normalization(data).reset_index().drop('Date', axis=1)
    model.fit(data.drop('Category', axis=1), data['Category'], cat_features=('Date.1', 'is_weekend', 'is_deposit'))
    model.save_model('fitted_model.cbm')