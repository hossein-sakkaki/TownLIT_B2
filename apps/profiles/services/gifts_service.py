# apps/profiles/services/gifts_service.py

from apps.profiles.models import SpiritualGiftSurveyResponse
from apps.profiles.gift_constants import (
    WISDOM, TONGUES, TEACHING, SHEPHERDING, SERVANTHOOD,
    PROPHECY, MIRACLES, LEADERSHIP, KNOWLEDGE, INTERPRETATION_OF_TONGUES,
    HELPING, HEALING, GIVING, FAITH, EXHORTATION,
    EVANGELISM, DISCERNMENT, COMPASSION, APOSTLESHIP, ADMINISTRATION
)

# ---------------------------------------------------------------------
# Fixed global priority order for tie-breaking
# ---------------------------------------------------------------------
GIFT_PRIORITY = [
    APOSTLESHIP,
    SHEPHERDING,
    TEACHING,
    PROPHECY,
    LEADERSHIP,
    EVANGELISM,
    WISDOM,
    HEALING,
    ADMINISTRATION,
    FAITH,
    TONGUES,
    SERVANTHOOD,
    MIRACLES,
    KNOWLEDGE,
    INTERPRETATION_OF_TONGUES,
    HELPING,
    GIVING,
    EXHORTATION,
    DISCERNMENT,
    COMPASSION,
]

# Build index lookup: lower index = higher priority
GIFT_PRIORITY_INDEX = {gift: i for i, gift in enumerate(GIFT_PRIORITY)}


# ---------------------------------------------------------------------
# Calculate raw scores for all gifts
# ---------------------------------------------------------------------
def calculate_spiritual_gifts_scores(member):
    scores = {}

    # mapping of each gift → list of question numbers
    gifts_questions = {
        WISDOM: [1, 21, 41, 61, 81, 101, 121, 141, 161, 181],
        KNOWLEDGE: [2, 22, 42, 62, 82, 102, 122, 142, 162, 182],
        ADMINISTRATION: [3, 23, 43, 63, 83, 103, 123, 143, 163, 183],
        APOSTLESHIP: [4, 24, 44, 64, 84, 104, 124, 144, 164, 184],
        SHEPHERDING: [5, 25, 45, 65, 85, 105, 125, 145, 165, 185],
        FAITH: [6, 26, 46, 66, 86, 106, 126, 146, 166, 186],
        MIRACLES: [7, 27, 47, 67, 87, 107, 127, 147, 167, 187],
        PROPHECY: [8, 28, 48, 68, 88, 108, 128, 148, 168, 188],
        LEADERSHIP: [9, 29, 49, 69, 89, 109, 129, 149, 169, 189],
        GIVING: [10, 30, 50, 70, 90, 110, 130, 150, 170, 190],
        COMPASSION: [11, 31, 51, 71, 91, 111, 131, 151, 171, 191],
        HEALING: [12, 32, 52, 72, 92, 112, 132, 152, 172, 192],
        DISCERNMENT: [13, 33, 53, 73, 93, 113, 133, 153, 173, 193],
        TEACHING: [14, 34, 54, 74, 94, 114, 134, 154, 174, 194],
        HELPING: [15, 35, 55, 75, 95, 115, 135, 155, 175, 195],
        EVANGELISM: [16, 36, 56, 76, 96, 116, 136, 156, 176, 196],
        SERVANTHOOD: [17, 37, 57, 77, 97, 117, 137, 157, 177, 197],
        EXHORTATION: [18, 38, 58, 78, 98, 118, 138, 158, 178, 198],
        TONGUES: [19, 39, 59, 79, 99, 119, 139, 159, 179, 199],
        INTERPRETATION_OF_TONGUES: [20, 40, 60, 80, 100, 120, 140, 160, 180, 200],
    }

    # fetch responses
    responses = SpiritualGiftSurveyResponse.objects.filter(member=member) \
        .values('question_number', 'answer')

    response_dict = {r['question_number']: r['answer'] for r in responses}

    # compute total scores
    for gift_name, questions in gifts_questions.items():
        total_score = sum(response_dict.get(q, 0) for q in questions)
        scores[gift_name] = total_score

    return scores


# ---------------------------------------------------------------------
# Determine exact top-k gifts using score + custom priority order
# ---------------------------------------------------------------------
def calculate_top_k_gifts(scores, k=4):
    """
    Sort gifts by:
    1) Score (desc)
    2) Custom gift priority order when scores tie
    Returns exactly k gift names.
    """

    items = list(scores.items())

    # sort using score desc + priority asc
    items.sort(
        key=lambda x: (
            -x[1],                               # score desc
            GIFT_PRIORITY_INDEX.get(x[0], 999),  # custom priority
        )
    )

    # return top-k names
    return [name for name, _ in items[:k]]


# ---------------------------------------------------------------------
# Public wrapper for top-4 gifts
# ---------------------------------------------------------------------
def calculate_top_4_gifts(scores):
    return calculate_top_k_gifts(scores, k=4)
