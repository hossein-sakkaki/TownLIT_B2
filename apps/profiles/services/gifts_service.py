from apps.profiles.models import SpiritualGiftSurveyResponse
from apps.profiles.gift_constants import (
                WISDOM, TONGUES, TEACHING, SHEPHERDING, SERVANTHOOD,
                PROPHECY, MIRACLES, LEADERSHIP, KNOWLEDGE, INTERPRETATION_OF_TONGUES,
                HELPING, HEALING, GIVING, FAITH, EXHORTATION,
                EVANGELISM, DISCERNMENT, COMPASSION, APOSTLESHIP, ADMINISTRATION
            )


# MEMBER'S GIFT Calculate --------------------------------------------------------
def calculate_spiritual_gifts_scores(member):
    scores = {}
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
    
    responses = SpiritualGiftSurveyResponse.objects.filter(member=member).values('question_number', 'answer')
    response_dict = {response['question_number']: response['answer'] for response in responses}
    
    for gift_name, questions in gifts_questions.items():
        total_score = sum(response_dict.get(question_number, 0) for question_number in questions)
        scores[gift_name] = total_score

    return scores


# Calculate Top 3 Gifts -------------------------------------------------------------------
from apps.profiles.models import SpiritualGiftSurveyResponse
from apps.profiles.gift_constants import (
                WISDOM, TONGUES, TEACHING, SHEPHERDING, SERVANTHOOD,
                PROPHECY, MIRACLES, LEADERSHIP, KNOWLEDGE, INTERPRETATION_OF_TONGUES,
                HELPING, HEALING, GIVING, FAITH, EXHORTATION,
                EVANGELISM, DISCERNMENT, COMPASSION, APOSTLESHIP, ADMINISTRATION
            )


# MEMBER'S GIFT Calculate --------------------------------------------------------
def calculate_spiritual_gifts_scores(member):
    scores = {}
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
    
    responses = SpiritualGiftSurveyResponse.objects.filter(member=member).values('question_number', 'answer')
    response_dict = {response['question_number']: response['answer'] for response in responses}
    
    for gift_name, questions in gifts_questions.items():
        total_score = sum(response_dict.get(question_number, 0) for question_number in questions)
        scores[gift_name] = total_score

    return scores


# Calculate Top K Gifts (default=4) -------------------------------------------
def calculate_top_k_gifts(scores, k=4):
    # sort by score desc, then name asc (stable & deterministic)
    sorted_gifts = sorted(scores.items(), key=lambda x: (-x[1], x[0]))
    if not sorted_gifts:
        return []

    n = len(sorted_gifts)
    if n <= k:
        # fewer gifts than k -> just return what we have (names only)
        return [name for name, _ in sorted_gifts]

    # build the first k-1 individually
    top = [name for name, _ in sorted_gifts[:k-1]]

    # boundary tie check: only group when the tie is exactly at the kth slot,
    # and NOT already tied with the (k-1)th (to preserve prior pattern)
    kth_score = sorted_gifts[k-1][1]
    prev_score = sorted_gifts[k-2][1] if k > 1 else None
    next_score = sorted_gifts[k][1] if n > k else None

    if next_score is not None and kth_score == next_score and (prev_score is None or kth_score != prev_score):
        # collect all names at the kth score from the boundary onward
        tied_kth = [name for name, score in sorted_gifts[k-1:] if score == kth_score]
        tied_kth = tied_kth[:2]  # keep list short (same pattern you used before)
        top.append(tied_kth)     # last slot becomes a list (caller unpacks)
    else:
        # no boundary tie -> take the kth individually
        top.append(sorted_gifts[k-1][0])

    # return exactly k "slots" (where the last may be a list to represent a tie)
    return top[:k]


# Backward-compatible helper for clarity in your codebase ----------------------
def calculate_top_4_gifts(scores):
    # small wrapper to signal "we pick 4" without changing other call sites later
    return calculate_top_k_gifts(scores, k=4)
