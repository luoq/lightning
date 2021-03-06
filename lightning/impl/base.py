# Author: Mathieu Blondel
# License: BSD

import numpy as np
from sklearn.base import BaseEstimator as _BaseEstimator
from sklearn.base import ClassifierMixin, RegressorMixin
from sklearn.preprocessing import LabelBinarizer
from sklearn.preprocessing import LabelEncoder
from sklearn.utils.extmath import safe_sparse_dot, softmax

from .randomkit import RandomState


class BaseEstimator(_BaseEstimator):

    def _get_random_state(self):
        return RandomState(seed=self.random_state)

    def n_nonzero(self, percentage=False):
        if hasattr(self, "coef_"):
            coef = self.coef_
        else:
            coef = self.dual_coef_

        n_nz = np.sum(np.sum(coef != 0, axis=0, dtype=bool))

        if percentage:
            if hasattr(self, "support_vectors_") and \
               self.support_vectors_ is not None:
                n_nz /= float(self.n_samples_)
            else:
                n_nz /= float(coef.shape[1])

        return n_nz


class BaseClassifier(BaseEstimator, ClassifierMixin):

    def predict_proba(self, X):
        if len(self.classes_) > 2:
            if self.loss == 'log':
                if self.multiclass:#multinomial logistic regression
                    return softmax(self.decision_function(X), copy=False)
                else: # one-vs-rest logistic regression
                    prob = self.decision_function(X)
                    prob *= -1
                    np.exp(prob, prob)
                    prob += 1
                    np.reciprocal(prob, prob)
                    # OvR normalization, like LibLinear's predict_probability
                    prob /= prob.sum(axis=1).reshape((prob.shape[0], -1))
                    return prob
            else:
                raise NotImplementedError("predict_(log_)proba not implemented")

        if self.loss == "log":
            df = self.decision_function(X).ravel()
            prob = 1.0 / (1.0 + np.exp(-df))
        elif self.loss == "modified_huber":
            df = self.decision_function(X).ravel()
            prob = np.minimum(1, np.maximum(-1, df))
            prob += 1
            prob /= 2
        else:
            raise NotImplementedError("predict_(log_)proba only supported when"
                                      " loss='log' or loss='modified_huber' "
                                      "(%s given)" % self.loss)

        out = np.zeros((X.shape[0], 2), dtype=np.float64)
        out[:, 1] = prob
        out[:, 0] = 1 - prob

        return out

    def _set_label_transformers(self, y, neg_label=-1):
        self.label_encoder_ = LabelEncoder()
        y = self.label_encoder_.fit_transform(y).astype(np.int32)
        self.classes_ = self.label_encoder_.classes_

        self.label_binarizer_ = LabelBinarizer(neg_label=neg_label,
                                               pos_label=1)
        self.label_binarizer_.fit(y)
        n_classes = len(self.label_binarizer_.classes_)
        n_vectors = 1 if n_classes <= 2 else n_classes

        return y, n_classes, n_vectors

    def decision_function(self, X):
        if self.coef_.shape[0] > 2 or self.coef_.shape[0] == 1:
            pred = safe_sparse_dot(X, self.coef_.T)
        elif self.coef_.shape[0] == 2:
            pred = safe_sparse_dot(X, self.coef_[1:2].T)
        else:
            raise RuntimeError('nrow of coef_ must >= 2')
        if hasattr(self, "intercept_"):
            pred += self.intercept_
        return pred

    def predict(self, X):
        pred = self.decision_function(X)
        out = self.label_binarizer_.inverse_transform(pred)

        if hasattr(self, "label_encoder_"):
            out = self.label_encoder_.inverse_transform(out)

        return out


class BaseRegressor(BaseEstimator, RegressorMixin):

    def predict(self, X):
        pred = safe_sparse_dot(X, self.coef_.T)

        if hasattr(self, "intercept_"):
            pred += self.intercept_

        if not self.outputs_2d_:
            pred = pred.ravel()

        return pred
