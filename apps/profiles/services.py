from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.profiles.gift_constants import (
                WISDOM, TONGUES, TEACHING, SHEPHERDING, SERVANTHOOD,
                PROPHECY, MIRACLES, LEADERSHIP, KNOWLEDGE, INTERPRETATION_OF_TONGUES,
                HELPING, HEALING, GIVING, FAITH, EXHORTATION,
                EVANGELISM, DISCERNMENT, COMPASSION, APOSTLESHIP, ADMINISTRATION
            )
from apps.profiles.constants import RECIPROCAL_FELLOWSHIP_CHOICES
import logging

logger = logging.getLogger(__name__)

# FRIENDSHIP Manager ----------------------------------------------------------
def add_symmetric_friendship(user1, user2):
    from .models import Friendship
    try:
        with transaction.atomic():
            existing_friendship = Friendship.objects.filter(
                from_user=user1,
                to_user=user2,
                status='accepted'
            )
            if not existing_friendship.exists():
                Friendship.objects.create(from_user=user1, to_user=user2, status='accepted')

            # Check if the reverse accepted friendship exists
            reverse_friendship = Friendship.objects.filter(
                from_user=user2,
                to_user=user1,
                status='accepted'
            )
            if not reverse_friendship.exists():
                # Create a new reverse friendship
                Friendship.objects.create(from_user=user2, to_user=user1, status='accepted')

        return True
    except IntegrityError as e:
        logger.error(f"IntegrityError while creating friendship between {user1} and {user2}: {e}")
        return False


def remove_symmetric_friendship(initiator, counterpart):
    from .models import Friendship
    try:
        with transaction.atomic():
            # Update the friendship initiated by the initiator
            initiator_friendship = Friendship.objects.filter(
                from_user=initiator, to_user=counterpart, status='accepted'
            ).first()
            if initiator_friendship:
                initiator_friendship.status = 'deleted'
                initiator_friendship.deleted_at = timezone.now()
                initiator_friendship.is_active = False
                initiator_friendship.save()

            # Delete the friendship initiated by the counterpart
            counterpart_friendship = Friendship.objects.filter(
                from_user=counterpart, to_user=initiator, status='accepted'
            ).first()
            if counterpart_friendship:
                counterpart_friendship.delete()

        return True
    except IntegrityError as e:
        logger.error(f"IntegrityError while updating friendship status between {initiator} and {counterpart}: {e}")
        return False
    



# FELLOWSHIP Manager ----------------------------------------------------------
def add_symmetric_fellowship(from_user, to_user, fellowship_type, reciprocal_fellowship_type=None):
    from .models import Fellowship
    from django.db import IntegrityError

    valid_types = [choice[0] for choice in RECIPROCAL_FELLOWSHIP_CHOICES]

    if fellowship_type not in valid_types or (reciprocal_fellowship_type and reciprocal_fellowship_type not in valid_types):
        logger.error("Invalid fellowship type provided.")
        return False

    try:
        with transaction.atomic():
            # چک کردن وجود رابطه اصلی
            main_fellowship_exists = Fellowship.objects.filter(
                from_user=from_user,
                to_user=to_user,
                fellowship_type=fellowship_type,
                reciprocal_fellowship_type=reciprocal_fellowship_type
            ).exists()

            if not main_fellowship_exists:
                Fellowship.objects.create(
                    from_user=from_user,
                    to_user=to_user,
                    fellowship_type=fellowship_type,
                    reciprocal_fellowship_type=reciprocal_fellowship_type,
                    status='Accepted'
                )
                logger.info(f"Fellowship created: {from_user} -> {to_user} ({fellowship_type})")

            # چک کردن وجود رابطه متقارن
            if reciprocal_fellowship_type:
                reciprocal_fellowship_exists = Fellowship.objects.filter(
                    from_user=to_user,
                    to_user=from_user,
                    fellowship_type=reciprocal_fellowship_type,
                    reciprocal_fellowship_type=fellowship_type
                ).exists()

                if not reciprocal_fellowship_exists:
                    Fellowship.objects.create(
                        from_user=to_user,
                        to_user=from_user,
                        fellowship_type=reciprocal_fellowship_type,
                        reciprocal_fellowship_type=fellowship_type,
                        status='Accepted'
                    )
                    logger.info(f"Reciprocal fellowship created: {to_user} -> {from_user} ({reciprocal_fellowship_type})")

        return True
    except IntegrityError as e:
        logger.error(f"IntegrityError while adding symmetric fellowship: {e}")
        return False
    except Exception as e:
        logger.error(f"Unexpected error while adding symmetric fellowship: {e}")
        return False


def remove_symmetric_fellowship(from_user, to_user, relationship_type):
    from .models import Fellowship
    try:
        with transaction.atomic():
            # Delete the main relationship
            main_deleted = Fellowship.objects.filter(
                from_user=from_user,
                to_user=to_user,
                fellowship_type=relationship_type,
                status='Accepted'
            ).delete()
            logger.info(f"Main fellowship removed: {from_user} -> {to_user} ({relationship_type})")

            # Delete the reciprocal relationship
            reciprocal_deleted = Fellowship.objects.filter(
                from_user=to_user,
                to_user=from_user,
                reciprocal_fellowship_type=relationship_type,
                status='Accepted'
            ).delete()
            logger.info(f"Reciprocal fellowship removed: {to_user} -> {from_user} ({relationship_type})")

        return True
    except Exception as e:
        logger.error(f"Error while removing symmetric fellowship: {e}")
        return False


# MEMBER'S GIFT Calculate --------------------------------------------------------
def calculate_spiritual_gifts_scores(member):
    from .models import SpiritualGiftSurveyResponse
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
def calculate_top_3_gifts(scores):
    # Sort scores by value in descending order and then by name in ascending order
    sorted_gifts = sorted(scores.items(), key=lambda x: (-x[1], x[0]))

    # Extract scores of the top 4 gifts
    first_score = sorted_gifts[0][1]
    second_score = sorted_gifts[1][1]
    third_score = sorted_gifts[2][1]
    fourth_score = sorted_gifts[3][1]

    # Final list of top gifts
    top_gifts = []

    # Check for tied scores
    if first_score != second_score and second_score != third_score and third_score != fourth_score:
        # Case: No tied scores in the top four
        top_gifts.extend([sorted_gifts[0][0], sorted_gifts[1][0], sorted_gifts[2][0]])
    elif first_score == second_score or second_score == third_score:
        # Case: Tied scores in the first, second, or third positions
        top_gifts.extend([sorted_gifts[0][0], sorted_gifts[1][0], sorted_gifts[2][0]])
    elif third_score == fourth_score:
        # Case: Tied scores in the third and fourth positions
        top_gifts.append(sorted_gifts[0][0])  # First gift
        top_gifts.append(sorted_gifts[1][0])  # Second gift
        third_tied_gifts = [gift for gift, score in sorted_gifts if score == third_score][:2]
        top_gifts.append(third_tied_gifts)  # Third gift as a shared option
        

    # Limit the result to the top 3 gifts
    return top_gifts[:3]

