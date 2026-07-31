# apps/journey_insights/question_bank/faith.py

from apps.journey_insights.constants import ReflectionDimension
from apps.journey_insights.question_bank.schema import choice, question


D = ReflectionDimension


QUESTIONS = [
    question(
        code="faith_attention_001",
        prompt="What most helps you make room for spiritual reflection?",
        dimension=D.FAITH,
        secondary_dimensions=[D.PEACE, D.REST],
        is_brand_core=True,
        metadata={"time_context": "general_pattern", "theme": "spiritual_practice"},
        choices=[
            choice(
                code="scripture_prayer",
                label="Scripture, prayer, or a familiar spiritual practice",
                base_score=3.46,
                weights={D.FAITH: 1.26, D.PEACE: 0.73, D.GROWTH: 0.54},
            ),
            choice(
                code="quiet_observation",
                label="Quiet attention to what is happening within and around me",
                base_score=3.34,
                weights={D.FAITH: 0.82, D.SELF_AWARENESS: 1.04, D.PEACE: 0.61},
            ),
            choice(
                code="shared_worship",
                label="Worship or reflection with other believers",
                base_score=3.49,
                weights={D.FAITH: 1.16, D.CONNECTION: 1.02, D.HOPE: 0.52},
            ),
            choice(
                code="acts_of_service",
                label="Serving someone in a concrete and thoughtful way",
                base_score=3.51,
                weights={D.FAITH: 0.96, D.COMPASSION: 1.18, D.PURPOSE: 0.72},
            ),
        ],
    ),
    question(
        code="faith_questions_002",
        prompt="When you carry an unresolved spiritual question, what response is most constructive?",
        dimension=D.FAITH,
        secondary_dimensions=[D.GROWTH, D.CONNECTION],
        difficulty=4,
        sensitivity=2,
        metadata={"time_context": "season", "theme": "questions"},
        choices=[
            choice(
                code="patient_prayer",
                label="Continue praying without pretending I already understand",
                base_score=3.52,
                weights={D.FAITH: 1.22, D.PEACE: 0.68, D.SELF_AWARENESS: 0.67},
            ),
            choice(
                code="study_context",
                label="Study Scripture carefully and consider its wider context",
                base_score=3.48,
                weights={D.FAITH: 1.14, D.GROWTH: 1.03, D.PURPOSE: 0.42},
            ),
            choice(
                code="seek_mature_guidance",
                label="Speak with a mature and trustworthy Christian",
                base_score=3.43,
                weights={D.FAITH: 0.98, D.CONNECTION: 1.06, D.GROWTH: 0.72},
            ),
            choice(
                code="live_known_truth",
                label="Keep practicing what is already clear while the question remains open",
                base_score=3.56,
                weights={D.FAITH: 1.17, D.PURPOSE: 0.92, D.RESILIENCE: 0.71},
            ),
        ],
    ),
    question(
        code="faith_daily_expression_003",
        prompt="Which ordinary action can most naturally express your faith?",
        dimension=D.FAITH,
        secondary_dimensions=[D.COMPASSION, D.PURPOSE],
        metadata={"time_context": "forward", "theme": "lived_faith"},
        choices=[
            choice(
                code="truth_with_grace",
                label="Speak truth with patience and respect",
                base_score=3.47,
                weights={D.FAITH: 0.96, D.COURAGE: 0.81, D.COMPASSION: 0.74},
            ),
            choice(
                code="reliable_work",
                label="Do ordinary work with honesty and care",
                base_score=3.42,
                weights={D.FAITH: 0.89, D.PURPOSE: 1.02, D.GROWTH: 0.52},
            ),
            choice(
                code="notice_excluded",
                label="Notice someone who may feel unseen or excluded",
                base_score=3.53,
                weights={D.FAITH: 0.91, D.COMPASSION: 1.21, D.CONNECTION: 0.82},
            ),
            choice(
                code="receive_correction",
                label="Receive correction without immediately defending myself",
                base_score=3.45,
                weights={D.FAITH: 0.84, D.GROWTH: 1.12, D.SELF_AWARENESS: 0.78},
            ),
        ],
    ),
    question(
        code="faith_trust_004",
        prompt="What does trust look like when you do not have a clear outcome?",
        dimension=D.FAITH,
        secondary_dimensions=[D.HOPE, D.PEACE],
        difficulty=4,
        metadata={"time_context": "general_pattern", "theme": "trust"},
        choices=[
            choice(
                code="responsible_action",
                label="Act responsibly while accepting what is beyond my control",
                base_score=3.54,
                weights={D.FAITH: 1.08, D.PURPOSE: 0.96, D.PEACE: 0.72},
            ),
            choice(
                code="honest_prayer",
                label="Bring both confidence and uncertainty honestly into prayer",
                base_score=3.58,
                weights={D.FAITH: 1.24, D.SELF_AWARENESS: 0.88, D.PEACE: 0.61},
            ),
            choice(
                code="community_support",
                label="Remain connected to the community instead of carrying everything alone",
                base_score=3.49,
                weights={D.FAITH: 0.97, D.CONNECTION: 1.13, D.RESILIENCE: 0.62},
            ),
            choice(
                code="faithful_waiting",
                label="Keep doing what is good even when progress is difficult to measure",
                base_score=3.55,
                weights={D.FAITH: 1.14, D.RESILIENCE: 0.92, D.HOPE: 0.78},
            ),
        ],
    ),
    question(
        code="faith_community_005",
        prompt="What contribution from Christian community is most valuable in a demanding season?",
        dimension=D.FAITH,
        secondary_dimensions=[D.CONNECTION, D.RESILIENCE],
        metadata={"time_context": "season", "theme": "community"},
        choices=[
            choice(
                code="shared_prayer",
                label="People who pray with me and remain present",
                base_score=3.51,
                weights={D.FAITH: 1.07, D.CONNECTION: 1.13, D.HOPE: 0.62},
            ),
            choice(
                code="wise_challenge",
                label="People who lovingly challenge my assumptions",
                base_score=3.47,
                weights={D.FAITH: 0.88, D.GROWTH: 1.16, D.CONNECTION: 0.63},
            ),
            choice(
                code="practical_care",
                label="People who offer concrete help without making me feel small",
                base_score=3.54,
                weights={D.FAITH: 0.82, D.COMPASSION: 1.21, D.CONNECTION: 0.91},
            ),
            choice(
                code="shared_memory",
                label="People who remind me of truth and hope when I lose perspective",
                base_score=3.57,
                weights={D.FAITH: 1.09, D.HOPE: 1.06, D.RESILIENCE: 0.71},
            ),
        ],
    ),
]


QUESTIONS += [
    question(
        code="faith_dry_season_006",
        prompt="What can faithfulness look like when spiritual feelings are quiet or absent?",
        dimension=D.FAITH,
        secondary_dimensions=[D.RESILIENCE, D.PURPOSE],
        difficulty=5,
        sensitivity=3,
        metadata={"time_context": "spiritual_season", "theme": "spiritual_dryness"},
        choices=[
            choice(
                code="continue_simple_practice",
                label="Continue a simple practice without pretending to feel more than I do",
                base_score=3.59,
                weights={D.FAITH: 1.24, D.RESILIENCE: 1.03, D.SELF_AWARENESS: 0.72},
            ),
            choice(
                code="honest_prayer_silence",
                label="Bring honesty, silence, or unanswered questions into prayer",
                base_score=3.62,
                weights={D.FAITH: 1.28, D.SELF_AWARENESS: 1.04, D.PEACE: 0.69},
            ),
            choice(
                code="remain_in_community",
                label="Remain connected to Christian community rather than withdrawing completely",
                base_score=3.56,
                weights={D.FAITH: 1.09, D.CONNECTION: 1.16, D.RESILIENCE: 0.67},
            ),
            choice(
                code="practice_known_good",
                label="Continue practicing what is good even without emotional certainty",
                base_score=3.61,
                weights={D.FAITH: 1.21, D.PURPOSE: 1.08, D.COURAGE: 0.61},
            ),
        ],
    ),
    question(
        code="faith_wound_007",
        prompt="When a painful experience affects your spiritual trust, what response feels most truthful?",
        dimension=D.FAITH,
        secondary_dimensions=[D.SELF_AWARENESS, D.RESILIENCE],
        difficulty=5,
        sensitivity=5,
        allow_for_new_users=False,
        minimum_journey_entries=8,
        metadata={"time_context": "painful_spiritual_experience", "theme": "spiritual_wound"},
        choices=[
            choice(
                code="name_harm_clearly",
                label="Name the harm clearly without calling it spiritually necessary",
                base_score=3.64,
                weights={D.FAITH: 1.02, D.SELF_AWARENESS: 1.19, D.COURAGE: 0.96},
            ),
            choice(
                code="separate_god_human_failure",
                label="Carefully distinguish God from the failures of people or institutions",
                base_score=3.67,
                weights={D.FAITH: 1.22, D.GROWTH: 1.06, D.RESILIENCE: 0.81},
            ),
            choice(
                code="seek_safe_guidance",
                label="Seek spiritually mature guidance that does not pressure or silence me",
                base_score=3.61,
                weights={D.FAITH: 1.13, D.CONNECTION: 1.14, D.COMPASSION: 0.73},
            ),
            choice(
                code="allow_slow_rebuilding",
                label="Allow trust to rebuild slowly rather than forcing certainty",
                base_score=3.65,
                weights={D.FAITH: 1.17, D.PEACE: 1.04, D.RESILIENCE: 0.91},
            ),
        ],
    ),
    question(
        code="faith_strength_008",
        prompt="Which spiritual strength do you most want to practice rather than merely admire?",
        dimension=D.FAITH,
        secondary_dimensions=[D.GROWTH, D.PURPOSE],
        metadata={"time_context": "forward", "theme": "practiced_character"},
        choices=[
            choice(
                code="patient_love",
                label="Patient love when another person is difficult",
                base_score=3.58,
                weights={D.FAITH: 1.08, D.COMPASSION: 1.21, D.RESILIENCE: 0.62},
            ),
            choice(
                code="truthful_humility",
                label="Truthfulness that remains humble and teachable",
                base_score=3.62,
                weights={D.FAITH: 1.13, D.GROWTH: 1.12, D.COURAGE: 0.74},
            ),
            choice(
                code="steady_hope",
                label="Steady hope that does not deny hardship",
                base_score=3.61,
                weights={D.FAITH: 1.16, D.HOPE: 1.19, D.SELF_AWARENESS: 0.51},
            ),
            choice(
                code="quiet_service",
                label="Quiet service that does not depend on recognition",
                base_score=3.64,
                weights={D.FAITH: 1.18, D.COMPASSION: 1.12, D.PURPOSE: 0.81},
            ),
        ],
    ),
    question(
        code="faith_guilt_009",
        prompt="What helps you distinguish responsible conviction from destructive shame?",
        dimension=D.FAITH,
        secondary_dimensions=[D.SELF_AWARENESS, D.GROWTH],
        difficulty=5,
        sensitivity=4,
        metadata={"time_context": "moral_reflection", "theme": "conviction_and_shame"},
        choices=[
            choice(
                code="specific_not_total",
                label="Conviction identifies something specific; shame condemns the whole person",
                base_score=3.66,
                weights={D.FAITH: 1.14, D.SELF_AWARENESS: 1.23, D.GROWTH: 0.79},
            ),
            choice(
                code="repair_path",
                label="Conviction points toward repentance and repair; shame offers no path forward",
                base_score=3.69,
                weights={D.FAITH: 1.26, D.GROWTH: 1.14, D.HOPE: 0.82},
            ),
            choice(
                code="truth_with_mercy",
                label="Healthy correction can hold truth and mercy together",
                base_score=3.67,
                weights={D.FAITH: 1.21, D.COMPASSION: 1.08, D.PEACE: 0.63},
            ),
            choice(
                code="seek_wise_discernment",
                label="When uncertain, I can seek wise and trustworthy discernment",
                base_score=3.58,
                weights={D.FAITH: 1.08, D.CONNECTION: 0.94, D.GROWTH: 0.91},
            ),
        ],
    ),
    question(
        code="faith_gift_010",
        prompt="Which ability or gift would you like to use more faithfully for the good of others?",
        dimension=D.FAITH,
        secondary_dimensions=[D.PURPOSE, D.COMPASSION],
        metadata={"time_context": "forward", "theme": "gifts_and_service"},
        choices=[
            choice(
                code="listening",
                label="My ability to listen and make space for another person",
                base_score=3.55,
                weights={D.FAITH: 0.96, D.CONNECTION: 1.17, D.COMPASSION: 1.04},
            ),
            choice(
                code="creating",
                label="My ability to create, build, or communicate something meaningful",
                base_score=3.52,
                weights={D.FAITH: 0.91, D.PURPOSE: 1.16, D.GROWTH: 0.72},
            ),
            choice(
                code="organizing",
                label="My ability to bring order and reliability to shared work",
                base_score=3.49,
                weights={D.FAITH: 0.88, D.PURPOSE: 1.18, D.CONNECTION: 0.54},
            ),
            choice(
                code="encouraging",
                label="My ability to strengthen hope and courage in others",
                base_score=3.61,
                weights={D.FAITH: 1.02, D.HOPE: 1.16, D.COMPASSION: 0.92},
            ),
        ],
    ),
]