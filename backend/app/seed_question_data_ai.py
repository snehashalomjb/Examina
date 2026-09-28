"""AI, ML, NLP, and deep-learning concept cards."""

from __future__ import annotations

from app.db.models import QuestionCategory as Q

from .seed_question_catalog import fact as F
from .seed_question_catalog import subject

SUBJECTS = (
    subject(
        "ML101",
        "Machine Learning",
        "Supervised learning, evaluation, optimisation, neural methods, and clustering.",
        Q.TECHNICAL,
        (
            F("Supervised Learning", "training target", "Supervised learning fits a mapping from input examples to known target values.", "Regression and classification are both supervised-learning paradigms.", "Targets define the prediction objective and determine the suitable loss."),
            F("Model Evaluation", "validation set", "A validation set is used to select models and hyperparameters during development.", "The test set should remain untouched until final evaluation.", "Clean data separation prevents optimistic and misleading performance estimates."),
            F("Regression", "mean squared error", "Mean squared error is the average squared difference between prediction and target.", "MSE penalises larger errors more strongly than smaller errors.", "Choosing a scale-sensitive loss determines how errors influence training."),
            F("Classification", "decision threshold", "A classification threshold maps a predicted probability to a class label.", "Moving the threshold trades false positives against false negatives.", "Threshold selection aligns model outputs with the real cost of each error."),
            F("Optimisation", "gradient descent", "Gradient descent updates parameters opposite the gradient of the loss.", "The learning rate controls the size of each update.", "Stable optimisation is essential for models to learn within a feasible budget."),
            F("Generalisation", "overfitting", "Overfitting is good training performance paired with poor unseen-data performance.", "Regularisation and validation can reduce overfitting.", "Generalisation, not training fit, is the target of model development."),
        ),
    ),
    subject(
        "NLP101",
        "Natural Language Processing",
        "Tokenisation, embeddings, sequence models, attention, and language evaluation.",
        Q.TECHNICAL,
        (
            F("Tokenisation", "word token", "A word token is a language-specific unit intended to represent a word.", "Subword tokenisation can represent unseen words by composing familiar units.", "The token unit determines sequence length, vocabulary coverage, and model cost."),
            F("Preprocessing", "lemmatisation", "Lemmatisation maps an inflected word to a normalised dictionary form using vocabulary and context.", "Part-of-speech information can disambiguate a lemma.", "Text preprocessing balances lexical reduction against semantic fidelity."),
            F("Language Models", "bigram", "A bigram model represents the probability of a token given the immediately preceding token.", "An n-gram model conditions on a local window of preceding tokens.", "N-gram models provide a simple probabilistic baseline for language tasks."),
            F("Representations", "word embedding", "A word embedding maps a token to a dense vector in which useful similarity patterns can be learned.", "Similar embedding vectors can support nearest-neighbour operations.", "Dense representations let models operate on lexical similarity rather than raw strings."),
            F("Sequence Modelling", "recurrent bottleneck", "A fixed-size recurrent hidden state can become a bottleneck when encoding arbitrarily long sequences.", "Attention lets a decoder retrieve information directly from encoder states.", "Attention reduces compression and long-range dependency problems in sequence models."),
            F("Attention", "query-key-value projection", "An attention query is compared with keys to weight the corresponding values.", "Scaled dot-product attention divides scores by a square-root factor before softmax.", "Query-key-value attention supports content-aware information retrieval."),
        ),
    ),
    subject(
        "AI101",
        "Artificial Intelligence",
        "Search, constraint solving, games, knowledge representation, planning, and probabilistic AI.",
        Q.TECHNICAL,
        (
            F("Search", "breadth-first search", "Breadth-first search explores an unweighted state space in increasing path cost from the start.", "BFS uses a queue as its usual frontier.", "BFS can find a shortest path when every transition has equal cost."),
            F("Heuristic Search", "heuristic function", "A heuristic estimates the remaining cost from a state to a goal.", "An admissible heuristic never overestimates that remaining cost.", "Heuristic guidance can find a solution faster than uninformed expansion."),
            F("Constraint Satisfaction", "backtracking", "Backtracking undoes assignments that cannot lead to a consistent solution.", "Forward checking can prune incompatible values early.", "Constraint methods exploit domain restrictions instead of exploring every state."),
            F("Game Search", "alpha-beta pruning", "Alpha-beta pruning discards branches that cannot affect the final minimax decision.", "The alpha and beta bounds track the best choices for maximising and minimising players.", "Pruning preserves the minimax value while reducing searched branches."),
            F("Planning", "plan representation", "A classical plan is a sequence of actions whose preconditions become satisfied in order.", "The plan's final state should satisfy the goal conditions.", "Explicit action models separate possible actions from state-transition effects."),
            F("Probabilistic AI", "Bayesian network", "A Bayesian network represents variables and conditional dependencies with directed edges.", "Exact inference is difficult for large densely connected networks.", "Probabilistic graphs support reasoning under uncertainty with explicit dependencies."),
        ),
    ),
    subject(
        "DL101",
        "Deep Learning",
        "Neural-network training, convolution, recurrence, attention, and regularisation.",
        Q.TECHNICAL,
        (
            F("Neural Networks", "activation function", "A nonlinear activation lets a neural network learn nonlinear input-output relationships.", "ReLU outputs zero for negative inputs and the input for positive inputs.", "Nonlinearity distinguishes deep networks from linear regressions."),
            F("Computer Vision", "convolution", "A convolutional filter slides across local input regions and computes weighted sums.", "Shared filter weights let the same feature detector run at many positions.", "Local connectivity and weight sharing make convolutional models parameter-efficient."),
            F("Computer Vision", "pooling", "Pooling aggregates nearby activations and can reduce spatial resolution.", "Max pooling selects the largest value in each pooling window.", "Pooling enlarges the effective receptive field and adds limited translation tolerance."),
            F("Training", "backpropagation", "Backpropagation applies the chain rule to compute gradients through a network.", "An optimiser uses those gradients to update parameters.", "Correct gradient computation is foundational to efficient neural-network training."),
            F("Sequence Models", "LSTM gate", "An LSTM uses gates to regulate how information enters, remains in, and leaves cell state.", "LSTMs were designed to mitigate vanishing gradients in long sequences.", "Gated memory improves modelling of dependencies across long time spans."),
            F("Transformers", "self-attention", "Self-attention lets each token representation incorporate information from other tokens.", "Parallel attention paths shorten the path between distant sequence positions.", "Transformers scale sequence modelling by directly connecting token interactions."),
        ),
    ),
)
