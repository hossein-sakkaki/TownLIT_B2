# validators/usernameValidators/constants.py

MIN_USERNAME_LENGTH = 3
MAX_USERNAME_LENGTH = 40

USERNAME_REUSE_COOLDOWN_DAYS = 30

USERNAME_ALLOWED_PATTERN = r"^[a-z0-9._]+$"

RESERVED_USERNAMES = [
    "admin", "administrator", "root", "superuser", "system", "staff", "team",
    "support", "help", "helpdesk", "security", "moderator", "mod",
    "official", "verified", "service", "services", "account", "accounts",

    "townlit", "townlitadmin", "townlitadministrator", "townlitsupport",
    "townlithelp", "townlithelpdesk", "townlitsecurity", "townlitstaff",
    "townlitteam", "townlitofficial", "townlitverified", "townlitmoderator",
    "townlitservice", "townlitservices",

    "lit", "litcore", "litshield", "litverse", "litnetwork",

    "api", "www", "web", "app", "apps", "mobile", "ios", "android",
    "mail", "email", "smtp", "imap", "noreply", "no-reply", "postmaster",
    "webmaster", "contact", "info", "legal", "privacy", "terms",

    "login", "logout", "signup", "signin", "register", "auth", "oauth",
    "password", "reset", "verify", "verification",

    "profile", "profiles", "user", "users", "member", "members",
    "guest", "guests", "messenger", "messages", "chat", "group", "groups",

    "news", "blog", "announcement", "announcements", "notification",
    "notifications", "settings", "dashboard", "console", "panel",

    "owner", "founder", "ceo", "president", "manager", "director",
]

RESERVED_FRAGMENTS = [
    "townlit", "admin", "administrator", "superuser", "system", "support",
    "helpdesk", "security", "moderator", "official", "verified", "staff",
    "service", "litshield",
]

PROFANE_WORDS = [
    "fuck", "fucker", "fucking", "motherfucker", "shit", "bullshit",
    "bitch", "asshole", "bastard", "cunt", "slut", "whore", "dick",
    "cock", "pussy", "penis", "vagina", "sex", "porn", "porno", "xxx",
    "nude", "nudes", "dildo", "retard", "faggot", "nigger", "nigga",
    "twat", "wank", "piss", "damn",
]

HATE_EXTREMIST_WORDS = [
    "nazi", "hitler", "kkk", "klan", "whitepower", "racist", "supremacist",
    "supremacy", "terrorist", "terror", "isis", "alqaeda",
]

VIOLENCE_CRIME_WORDS = [
    "kill", "killer", "murder", "murderer", "suicide", "rape", "rapist",
    "abuse", "massacre", "bloodbath", "bomb", "gun", "weapon", "criminal",
    "fraud", "scam", "scammer", "hack", "hacker",
]

DRUG_WORDS = [
    "cocaine", "heroin", "meth", "weed", "marijuana", "ecstasy", "lsd",
    "crack", "dope", "stoned", "drug", "drugs",
]

SCAM_IMPERSONATION_WORDS = [
    "paypal", "amazon", "apple", "microsoft", "google", "facebook",
    "instagram", "telegram", "whatsapp", "visa", "mastercard", "bank",
    "banking", "payment", "wallet", "crypto", "bitcoin",
]

SACRED_USERNAMES = [
    "god", "jesus", "christ", "yahweh", "holyspirit", "holy_spirit",
]

BLOCKED_WORDS = (
    PROFANE_WORDS
    + HATE_EXTREMIST_WORDS
    + VIOLENCE_CRIME_WORDS
    + DRUG_WORDS
)