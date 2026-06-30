import numpy as np
from sklearn.naive_bayes import GaussianNB
from scipy.special import logsumexp

class WeightedGaussianNB(GaussianNB):
    def __init__(self, var_smoothing=1e-9, feature_weights=None):
        super().__init__(var_smoothing=var_smoothing)
        self.feature_weights = feature_weights

    def predict_log_proba(self, X):
        from sklearn.utils.validation import check_is_fitted
        check_is_fitted(self)
        
        X = np.asarray(X)
        n_samples, n_features = X.shape
        n_classes = len(self.classes_)
        
        log_prior = np.log(self.class_prior_)
        jll = np.zeros((n_samples, n_classes))
        
        for i in range(n_classes):
            theta = self.theta_[i]
            var = self.var_[i]
            
            log_prob_features = -0.5 * np.log(2 * np.pi * var) - 0.5 * ((X - theta) ** 2) / var
            
            if self.feature_weights is not None:
                weights = np.asarray(self.feature_weights)
                log_prob_features = log_prob_features * weights
                
            jll[:, i] = log_prior[i] + np.sum(log_prob_features, axis=1)
            
        log_prob = jll - logsumexp(jll, axis=1, keepdims=True)
        return log_prob

    def predict_proba(self, X):
        return np.exp(self.predict_log_proba(X))

    def predict(self, X):
        return self.classes_[np.argmax(self.predict_log_proba(X), axis=1)]
