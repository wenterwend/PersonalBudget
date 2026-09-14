import logging
import threading
from typing import List, Dict, Any, Optional
import uuid
from sqlmodel import Session, select
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.naive_bayes import MultinomialNB

from ..models import Transaction, TransactionSplit, Category

logger = logging.getLogger(__name__)

class MLCategorizer:
    def __init__(self):
        self.vectorizer: Optional[TfidfVectorizer] = None
        self.model: Optional[MultinomialNB] = None
        self.classes_: List[uuid.UUID] = []
        self.is_trained: bool = False
        self._lock = threading.Lock()

    def train(self, session: Session) -> bool:
        with self._lock:
            # Query confirmed transactions with a category (category_id IS NOT NULL)
            query = select(Transaction.raw_payee, TransactionSplit.category_id)\
                .join(TransactionSplit, Transaction.id == TransactionSplit.transaction_id)\
                .where(TransactionSplit.category_id.isnot(None))\
                .where(Transaction.is_ml_suggested == False)
                
            results = session.exec(query).all()
            
            if not results or len(results) < 2:
                self.is_trained = False
                return False

            raw_payees = [r[0] for r in results]
            category_ids = [str(r[1]) for r in results]
            
            unique_cats = set(category_ids)
            if len(unique_cats) < 2:
                self.is_trained = False
                return False

            try:
                vec = TfidfVectorizer(ngram_range=(1, 3), analyzer='char_wb', sublinear_tf=True)
                X = vec.fit_transform(raw_payees)
                clf = MultinomialNB(alpha=0.1)
                clf.fit(X, category_ids)

                self.vectorizer = vec
                self.model = clf
                self.classes_ = [uuid.UUID(c) for c in clf.classes_]
                self.is_trained = True
                logger.info(f"ML Categorizer trained on {len(raw_payees)} samples across {len(unique_cats)} categories.")
                return True
            except Exception as e:
                logger.error(f"Failed to train ML model: {e}")
                self.is_trained = False
                return False

    def predict(self, raw_payee: str, session: Session) -> Dict[str, Any]:
        with self._lock:
            if not self.is_trained or not self.vectorizer or not self.model or not raw_payee.strip():
                return {
                    "suggested_category_id": None,
                    "confidence": 0.0,
                    "is_high_confidence": False,
                    "top_suggestions": []
                }

            try:
                X = self.vectorizer.transform([raw_payee.strip()])
                probs = self.model.predict_proba(X)[0]
                
                categories = {c.id: c.name for c in session.exec(select(Category)).all()}

                paired = []
                for idx, prob in enumerate(probs):
                    cat_id = self.classes_[idx]
                    paired.append({
                        "category_id": cat_id,
                        "category_name": categories.get(cat_id, "Unknown"),
                        "confidence": float(round(prob, 4))
                    })
                
                paired.sort(key=lambda x: x["confidence"], reverse=True)
                top_suggestions = paired[:3]

                best = top_suggestions[0] if top_suggestions else None
                is_high_confidence = False
                suggested_cat_id = None
                best_confidence = 0.0

                if best and best["confidence"] >= 0.70:
                    is_high_confidence = True
                    suggested_cat_id = best["category_id"]
                    best_confidence = best["confidence"]

                return {
                    "suggested_category_id": suggested_cat_id,
                    "confidence": best_confidence if is_high_confidence else (best["confidence"] if best else 0.0),
                    "is_high_confidence": is_high_confidence,
                    "top_suggestions": top_suggestions
                }
            except Exception as e:
                logger.error(f"Error during ML prediction: {e}")
                return {
                    "suggested_category_id": None,
                    "confidence": 0.0,
                    "is_high_confidence": False,
                    "top_suggestions": []
                }

# Global singleton instance
ml_categorizer = MLCategorizer()
