"""Run a small five-well example: python quick_test.py (or Run in Spyder).

Fits one model per target on Wells 1-3 and predicts Wells 4-5. Requires only
requirements.txt; no pre-generated data, saved models or manuscript is needed.
Temporary files are removed automatically; the included results are unchanged.
"""
from pathlib import Path
import tempfile
import sys

PROJECT = Path(__file__).resolve().parent
if str(PROJECT) not in sys.path:
    sys.path.insert(0, str(PROJECT))

import joblib
import numpy as np
import pandas as pd
from sklearn.metrics import accuracy_score, r2_score
from threadpoolctl import threadpool_limits
from synthetic_data import generate, FEATURES, TARGETS, FACIES, DEV_WELLS, APP_WELLS
from models import make_model, NAMES
from apply_models import apply


def quick_test():
    data = generate(n=120, seed=42)
    pd.testing.assert_frame_equal(data, generate(n=120, seed=42))
    train = data[data.Well.isin(DEV_WELLS)].copy()
    test = data[data.Well.isin(APP_WELLS)].copy()
    if len(train) != 360 or len(test) != 240 or set(train.Well) & set(test.Well):
        raise AssertionError('Expected three training wells and two separate test wells.')
    examples = {'Facies': 4, 'Porosity': 26, 'Permeability': 13}
    expected = {}
    scores = []
    with tempfile.TemporaryDirectory(prefix='five_well_quick_test_') as folder:
        folder = Path(folder)
        for task, number in examples.items():
            model = make_model(number, task, seed=42)
            model.fit(train[FEATURES], train[task])
            pred = model.predict(test[FEATURES])
            if pred.shape != (240,) or not np.isfinite(pred).all():
                raise AssertionError(f'{task}: expected 240 finite predictions.')
            if task == 'Facies' and not set(pred).issubset(set(range(4))):
                raise AssertionError('Unexpected facies class.')
            if task == 'Permeability' and not (pred > 0).all():
                raise AssertionError('Permeability predictions must be positive.')
            expected[task + '_predicted'] = pred
            scores.append({'Target': task, 'Model': NAMES[number],
                           'Metric': 'Accuracy' if task == 'Facies' else 'R2',
                           'Score': accuracy_score(test[task], pred) if task == 'Facies'
                           else r2_score(test[task], pred)})
            joblib.dump(dict(model=model, features=FEATURES, task=task,
                             number=number, name=NAMES[number], facies=FACIES),
                        folder / (task.lower() + '.joblib'))
        # Confirm prediction works from logs alone after saving/reloading models.
        test[['Well', 'Depth_m', *FEATURES]].to_csv(folder/'logs.csv', index=False)
        apply(folder/'logs.csv', folder, folder/'predictions.csv')
        reloaded = pd.read_csv(folder/'predictions.csv')
        for column, values in expected.items():
            np.testing.assert_allclose(reloaded[column], values, rtol=1e-9, atol=1e-9)
    print(pd.DataFrame(scores).to_string(index=False, float_format=lambda x: f'{x:.4f}'))
    print('PASS: 5 synthetic wells; 3 training wells; 2 held-out test wells; '
          '3 models; 240 test rows; saved-model predictions verified.')
    return pd.DataFrame(scores)


if __name__ == '__main__':
    with threadpool_limits(limits=1):
        quick_test_scores = quick_test()
