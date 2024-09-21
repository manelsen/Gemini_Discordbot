import nltk
from nltk.tokenize import word_tokenize
from nltk.corpus import stopwords
from nltk.sentiment import SentimentIntensityAnalyzer
import numpy as np

# Inicialização do SentimentIntensityAnalyzer
sia = SentimentIntensityAnalyzer()

def preprocess_text(text):
    tokens = word_tokenize(text.lower())
    stop_words = set(stopwords.words('english'))
    return [word for word in tokens if word.isalnum() and word not in stop_words]

def calculate_tf_idf(documents):
    word_freq = {}
    doc_freq = {}
    for doc in documents:
        words = set(doc)
        for word in words:
            doc_freq[word] = doc_freq.get(word, 0) + 1
        for word in doc:
            word_freq[word] = word_freq.get(word, 0) + 1
    
    idf = {word: np.log(len(documents) / freq) for word, freq in doc_freq.items()}
    return {word: freq * idf[word] for word, freq in word_freq.items()}

def detect_emotional_moments(text):
    sentiment_scores = sia.polarity_scores(text)
    compound_score = sentiment_scores['compound']
    
    if compound_score > 0.5:
        return True, "positivo"
    elif compound_score < -0.5:
        return True, "negativo"
    else:
        return False, "neutro"