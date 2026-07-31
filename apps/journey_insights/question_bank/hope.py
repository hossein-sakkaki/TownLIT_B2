# apps/journey_insights/question_bank/hope.py

from apps.journey_insights.constants import ReflectionDimension
from apps.journey_insights.question_bank.schema import choice, question


D = ReflectionDimension


QUESTIONS = [
    question(
        code="hope_next_step_001",
        prompt="When the future feels unclear, what helps you take the next faithful step?",
        dimension=D.HOPE,
        secondary_dimensions=[D.FAITH, D.COURAGE],
        is_brand_core=True,
        metadata={"time_context": "general_pattern", "theme": "uncertainty"},
        choices=[
            choice(
                code="small_responsibility",
                label="Focusing on the responsibility already in front of me",
                base_score=3.42,
                weights={D.HOPE: 0.94, D.PURPOSE: 1.01, D.COURAGE: 0.52},
            ),
            choice(
                code="remember_faithfulness",
                label="Remembering ways I have been carried through uncertainty before",
                base_score=3.48,
                weights={D.HOPE: 1.18, D.FAITH: 1.02, D.RESILIENCE: 0.66},
            ),
            choice(
                code="seek_wisdom",
                label="Seeking wisdom from someone whose judgment I trust",
                base_score=3.37,
                weights={D.HOPE: 0.72, D.CONNECTION: 0.94, D.GROWTH: 0.68},
            ),
            choice(
                code="remain_open",
                label="Remaining open without demanding an immediate answer",
                base_score=3.45,
                weights={D.HOPE: 1.06, D.PEACE: 0.83, D.FAITH: 0.61},
            ),
        ],
    ),
    question(
        code="hope_recent_sign_002",
        prompt="Which kind of sign most often renews your hope?",
        dimension=D.HOPE,
        secondary_dimensions=[D.CONNECTION, D.GROWTH],
        metadata={"time_context": "general_pattern", "theme": "renewal"},
        choices=[
            choice(
                code="changed_person",
                label="Seeing a person grow in a way I did not expect",
                base_score=3.46,
                weights={D.HOPE: 1.12, D.CONNECTION: 0.74, D.GROWTH: 0.78},
            ),
            choice(
                code="small_beginning",
                label="A small beginning that could become something more",
                base_score=3.36,
                weights={D.HOPE: 1.18, D.PURPOSE: 0.62, D.GROWTH: 0.58},
            ),
            choice(
                code="enduring_goodness",
                label="Goodness that remains present during difficulty",
                base_score=3.51,
                weights={D.HOPE: 1.24, D.FAITH: 0.76, D.RESILIENCE: 0.72},
            ),
            choice(
                code="honest_repair",
                label="Someone choosing honesty, apology, or repair",
                base_score=3.49,
                weights={D.HOPE: 0.98, D.CONNECTION: 1.03, D.COURAGE: 0.69},
            ),
        ],
    ),
    question(
        code="hope_delay_003",
        prompt="What is hardest for you about waiting for something important?",
        dimension=D.HOPE,
        secondary_dimensions=[D.PEACE, D.SELF_AWARENESS],
        difficulty=3,
        metadata={"time_context": "season", "theme": "waiting"},
        choices=[
            choice(
                code="unclear_timing",
                label="Not knowing how long the waiting will last",
                base_score=3.02,
                weights={D.HOPE: 0.34, D.PEACE: 0.32, D.SELF_AWARENESS: 0.88},
            ),
            choice(
                code="questioning_direction",
                label="Wondering whether I am waiting for the right thing",
                base_score=3.09,
                weights={D.HOPE: 0.41, D.PURPOSE: 0.62, D.SELF_AWARENESS: 0.82},
            ),
            choice(
                code="watching_others",
                label="Watching others move forward while I remain in place",
                base_score=2.97,
                weights={D.HOPE: 0.29, D.CONNECTION: 0.33, D.SELF_AWARENESS: 0.93},
            ),
            choice(
                code="sustaining_attention",
                label="Staying engaged without letting the waiting consume everything",
                base_score=3.24,
                weights={D.HOPE: 0.78, D.RESILIENCE: 0.84, D.PEACE: 0.48},
            ),
        ],
    ),
    question(
        code="hope_offer_004",
        prompt="How are you most able to offer hope to another person?",
        dimension=D.HOPE,
        secondary_dimensions=[D.COMPASSION, D.CONNECTION],
        metadata={"time_context": "general_pattern", "theme": "shared_hope"},
        choices=[
            choice(
                code="stay_present",
                label="Stay present without rushing to solve the problem",
                base_score=3.48,
                weights={D.HOPE: 0.82, D.COMPASSION: 1.18, D.CONNECTION: 0.94},
            ),
            choice(
                code="name_possibility",
                label="Help them notice a possibility they may have overlooked",
                base_score=3.34,
                weights={D.HOPE: 1.14, D.GROWTH: 0.72, D.CONNECTION: 0.54},
            ),
            choice(
                code="share_memory",
                label="Remind them of strength or faithfulness already present in their story",
                base_score=3.52,
                weights={D.HOPE: 1.08, D.RESILIENCE: 0.76, D.CONNECTION: 0.83},
            ),
            choice(
                code="practical_support",
                label="Offer practical help that makes the next step lighter",
                base_score=3.45,
                weights={D.HOPE: 0.72, D.COMPASSION: 1.13, D.PURPOSE: 0.66},
            ),
        ],
    ),
    question(
        code="hope_realism_005",
        prompt="Which statement best reflects healthy hope for you right now?",
        dimension=D.HOPE,
        secondary_dimensions=[D.FAITH, D.RESILIENCE],
        difficulty=4,
        metadata={"time_context": "current_season", "theme": "realistic_hope"},
        choices=[
            choice(
                code="good_without_control",
                label="I can seek what is good without controlling the outcome",
                base_score=3.49,
                weights={D.HOPE: 1.16, D.PEACE: 0.86, D.FAITH: 0.64},
            ),
            choice(
                code="pain_not_final",
                label="Pain can be real without being the whole story",
                base_score=3.55,
                weights={D.HOPE: 1.22, D.RESILIENCE: 0.93, D.SELF_AWARENESS: 0.48},
            ),
            choice(
                code="next_step_enough",
                label="I may not see the whole path, but I can take one honest step",
                base_score=3.51,
                weights={D.HOPE: 1.08, D.COURAGE: 0.94, D.PURPOSE: 0.67},
            ),
            choice(
                code="receive_support",
                label="Hope may include allowing others to carry part of the burden",
                base_score=3.47,
                weights={D.HOPE: 0.93, D.CONNECTION: 1.06, D.COMPASSION: 0.54},
            ),
        ],
    ),
]


QUESTIONS += [
    question(
        code="hope_disappointment_006",
        prompt="What helps hope remain honest after a deep disappointment?",
        dimension=D.HOPE,
        secondary_dimensions=[D.RESILIENCE, D.SELF_AWARENESS],
        difficulty=5,
        sensitivity=4,
        metadata={"time_context": "after_disappointment", "theme": "honest_hope"},
        choices=[
            choice(
                code="grieve_expectation",
                label="Allow myself to grieve what I genuinely hoped for",
                base_score=3.54,
                weights={D.HOPE: 0.91, D.SELF_AWARENESS: 1.12, D.RESILIENCE: 0.81},
            ),
            choice(
                code="separate_outcome_worth",
                label="Separate the lost outcome from the worth of my whole life",
                base_score=3.61,
                weights={D.HOPE: 1.18, D.RESILIENCE: 1.04, D.PEACE: 0.73},
            ),
            choice(
                code="look_for_new_path",
                label="Remain open to a good path that may look different from the one expected",
                base_score=3.58,
                weights={D.HOPE: 1.24, D.GROWTH: 0.94, D.COURAGE: 0.62},
            ),
            choice(
                code="receive_presence",
                label="Receive the presence of others even when they cannot fix the loss",
                base_score=3.56,
                weights={D.HOPE: 0.96, D.CONNECTION: 1.14, D.COMPASSION: 0.73},
            ),
        ],
    ),
    question(
        code="hope_hidden_strength_007",
        prompt="Which strength may be growing in you before the results become visible?",
        dimension=D.HOPE,
        secondary_dimensions=[D.GROWTH, D.RESILIENCE],
        metadata={"time_context": "current_season", "theme": "hidden_growth"},
        choices=[
            choice(
                code="greater_patience",
                label="Greater patience with a process I cannot rush",
                base_score=3.48,
                weights={D.HOPE: 0.94, D.RESILIENCE: 1.08, D.PEACE: 0.69},
            ),
            choice(
                code="clearer_boundaries",
                label="Clearer boundaries around what I can and cannot carry",
                base_score=3.53,
                weights={D.HOPE: 0.82, D.COURAGE: 1.02, D.REST: 0.91},
            ),
            choice(
                code="deeper_honesty",
                label="Greater honesty about what I feel and need",
                base_score=3.51,
                weights={D.HOPE: 0.88, D.SELF_AWARENESS: 1.18, D.COURAGE: 0.72},
            ),
            choice(
                code="steadier_commitment",
                label="A steadier commitment to what matters despite changing feelings",
                base_score=3.57,
                weights={D.HOPE: 1.02, D.PURPOSE: 1.14, D.RESILIENCE: 0.83},
            ),
        ],
    ),
    question(
        code="hope_fear_story_008",
        prompt="When fear predicts the future, which response helps you regain perspective?",
        dimension=D.HOPE,
        secondary_dimensions=[D.PEACE, D.SELF_AWARENESS],
        difficulty=4,
        metadata={"time_context": "general_pattern", "theme": "fear_prediction"},
        choices=[
            choice(
                code="separate_fact_prediction",
                label="Separate what I know from what I am predicting",
                base_score=3.55,
                weights={D.HOPE: 1.03, D.SELF_AWARENESS: 1.16, D.PEACE: 0.82},
            ),
            choice(
                code="identify_available_action",
                label="Identify one action available to me in the present",
                base_score=3.49,
                weights={D.HOPE: 1.08, D.PURPOSE: 0.96, D.COURAGE: 0.67},
            ),
            choice(
                code="remember_previous_endurance",
                label="Remember difficulties I have already endured or learned through",
                base_score=3.52,
                weights={D.HOPE: 1.13, D.RESILIENCE: 1.09, D.GRATITUDE: 0.51},
            ),
            choice(
                code="invite_other_perspective",
                label="Invite a trusted person to offer another perspective",
                base_score=3.47,
                weights={D.HOPE: 0.91, D.CONNECTION: 1.06, D.GROWTH: 0.63},
            ),
        ],
    ),
    question(
        code="hope_wounded_dream_009",
        prompt="What might caring for a wounded dream look like?",
        dimension=D.HOPE,
        secondary_dimensions=[D.COMPASSION, D.GROWTH],
        difficulty=5,
        sensitivity=4,
        allow_for_new_users=False,
        minimum_journey_entries=5,
        metadata={"time_context": "season", "theme": "wounded_dream"},
        choices=[
            choice(
                code="honor_meaning",
                label="Honor why the dream mattered before deciding what comes next",
                base_score=3.56,
                weights={D.HOPE: 1.04, D.SELF_AWARENESS: 1.08, D.COMPASSION: 0.72},
            ),
            choice(
                code="release_exact_form",
                label="Release its exact form while keeping what was good within it",
                base_score=3.62,
                weights={D.HOPE: 1.21, D.GROWTH: 1.03, D.PEACE: 0.74},
            ),
            choice(
                code="share_grief",
                label="Share the grief with someone who will not minimize it",
                base_score=3.58,
                weights={D.HOPE: 0.89, D.CONNECTION: 1.16, D.COMPASSION: 0.91},
            ),
            choice(
                code="allow_rest_before_direction",
                label="Allow a period of rest before demanding a new direction",
                base_score=3.55,
                weights={D.HOPE: 0.83, D.REST: 1.14, D.PEACE: 0.94},
            ),
        ],
    ),
    question(
        code="hope_offer_self_010",
        prompt="What hopeful truth would you most want to remember when you feel discouraged?",
        dimension=D.HOPE,
        secondary_dimensions=[D.RESILIENCE, D.FAITH],
        metadata={"time_context": "forward", "theme": "personal_reminder"},
        choices=[
            choice(
                code="progress_not_linear",
                label="Growth can be real even when progress is not linear",
                base_score=3.54,
                weights={D.HOPE: 1.17, D.GROWTH: 1.03, D.RESILIENCE: 0.71},
            ),
            choice(
                code="need_not_isolate",
                label="Difficulty does not mean I must become isolated",
                base_score=3.51,
                weights={D.HOPE: 1.06, D.CONNECTION: 1.08, D.COURAGE: 0.61},
            ),
            choice(
                code="small_step_counts",
                label="A small faithful step can still have meaning",
                base_score=3.58,
                weights={D.HOPE: 1.19, D.FAITH: 0.91, D.PURPOSE: 0.83},
            ),
            choice(
                code="story_unfinished",
                label="What I see now is not necessarily the final shape of the story",
                base_score=3.61,
                weights={D.HOPE: 1.24, D.RESILIENCE: 0.92, D.FAITH: 0.68},
            ),
        ],
    ),
]