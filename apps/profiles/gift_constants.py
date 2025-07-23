from django.utils.translation import gettext_lazy as _

# Sprituual Gifts List ---------------------------------------
WISDOM = 'wisdom'
KNOWLEDGE = 'knowledge'
ADMINISTRATION = 'administration'
APOSTLESHIP = 'apostleship'
SHEPHERDING = 'shepherding'
FAITH = 'faith'
MIRACLES = 'miracles'
PROPHECY = 'prophecy'
LEADERSHIP = 'leadership'
GIVING = 'giving'
COMPASSION = 'compassion'
HEALING = 'healing'
DISCERNMENT = 'discernment'
TEACHING = 'teaching'
HELPING = 'helping'
EVANGELISM = 'evangelism'
SERVANTHOOD = 'servanthood'
EXHORTATION = 'exhortation'
TONGUES = 'tongues'
INTERPRETATION_OF_TONGUES = 'interpretation_of_tongues'

GIFT_CHOICES = [
    (WISDOM, _('Wisdom')),
    (KNOWLEDGE, _('Knowledge')),
    (ADMINISTRATION, _('Administration')),
    (APOSTLESHIP, _('Apostleship')),
    (SHEPHERDING, _('Shepherding')),
    (FAITH, _('Faith')),
    (MIRACLES, _('Miracles')),
    (PROPHECY, _('Prophecy')),
    (LEADERSHIP, _('Leadership')),
    (GIVING, _('Giving')),
    (COMPASSION, _('Compassion')),
    (HEALING, _('Healing')),
    (DISCERNMENT, _('Discernment')),
    (TEACHING, _('Teaching')),
    (HELPING, _('Helping')),
    (EVANGELISM, _('Evangelism')),
    (SERVANTHOOD, _('Servanthood')),
    (EXHORTATION, _('Exhortation')),
    (TONGUES, _('Tongues')),
    (INTERPRETATION_OF_TONGUES, _('Interpretation of Tongues')),
]

# Sprituual Gifts Description ---------------------------------------
GIFT_DESCRIPTIONS = {
    ADMINISTRATION: _('The gift of organizing human and material resources for the work of Christ, including the ability to plan and work with people to delegate responsibilities, track progress, and evaluate the effectiveness of procedures. Administrators attend to details, communicate effectively, and take as much pleasure in working behind the scenes as they do in standing in the spotlight.'),
    APOSTLESHIP: _('The gift of spreading the gospel of Jesus Christ to other cultures and foreign lands. Apostleship is the missionary zeal that moves us from the familiar into uncharted territory to share the good news. Apostles embrace opportunities to learn foreign languages, visit other cultures, and go to places where people have not had the opportunity to hear the Christian message.'),
    COMPASSION: _('The gift of exceptional empathy with those in need that moves us to action. More than just concern, compassion demands that we share the suffering of others in order to connect the gospel truth with other realities of life. Compassion moves us beyond our comfort zones to offer practical, tangible aid to all God’s children, regardless of the worthiness of the recipients or the response we receive for our service.'),
    DISCERNMENT: _('The ability to separate truth from erroneous teachings and to rely on spiritual intuition to know what God is calling us to do. Discernment allows us to focus on what is truly important and to ignore that which deflects us from faithful obedience to God. Discernment aids us in knowing whom to listen to and whom to avoid.'),
    EVANGELISM: _('The ability to share the gospel of Jesus Christ with those who have not heard it before or with those who have not yet made a decision for Christ. This gift is manifested in both one-on-one situations and in group settings, both large and small. Evangelism is an intimate relationship with another person or persons that requires the sharing of personal faith experience and a call for a response of faith to God.'),
    EXHORTATION: _('The gift of exceptional encouragement. Exhorters see the silver lining in every cloud, offer deep and inspiring hope to the fellowship, and look for and commend the best in everyone. Exhorters empower others to feel good about themselves and to feel hopeful for the future. Exhorters are not concerned by appearances; they hold fast to what they know to be true and right and good.'),
    FAITH: _('The exceptional ability to hold fast to the truth of God in Jesus Christ in spite of pressures, problems, and obstacles to faithfulness. More than just belief, faith is a gift that empowers an individual or a group to hold fast to its identity in Christ in the face of any challenge. The gift of faith enables believers to rise above pressures and problems that might otherwise cripple them. Faith is characterized by an unshakable trust in God to deliver on God’s promises, no matter what.'),
    GIVING: _('The gift of the ability to manage money to the honor and glory of God. Beyond the regular response of gratitude to God that all believers make, those with the gift of giving can discern the best ways to put money to work, can understand the validity and practicality of appeals for funds, and can guide others in the most faithful methods for managing their financial concerns.'),
    HEALING: _('The gift of conducting God’s healing powers into the lives of God’s people. Physical, emotional, spiritual, and psychological healing are all ways that healers manifest this gift. Healers are prayerful, and they help people understand that healing is in the hands of God. Often their task is to bring about such understanding more than it is to simply erase negative symptoms. Some of the most powerful healers display some of the most heartbreaking afflictions themselves.'),
    HELPING: _('The gift of making sure that everything is ready for the work of Christ to occur. Helpers assist others to accomplish the work of God. These unsung heroes work behind the scenes and attend to details that others would rather not be bothered with. Helpers function faithfully, regardless of the credit or attention they receive. Helpers provide the framework upon which the ministry of the body of Christ is built.'),
    INTERPRETATION_OF_TONGUES: _('The gift of (1) the ability to interpret foreign languages without the necessity of formal study in order to communicate with those who have not heard the Christian message or who seek to understand, or (2) the ability to interpret the gift of tongues as a secret prayer language that communicates with God at a deep spiritual level. Both understandings of the gift of interpretation of tongues are communal in nature: the first extends the good news into the world; the second strengthens the faith within the fellowship.'),
    KNOWLEDGE: _('The gift of knowing the truth through faithful study of Scripture and the human situation. Knowledge provides the information necessary for the transformation of the world and the formation of the body of Christ. Those possessing the gift of knowledge challenge the fellowship to improve itself through study, reading of Scripture, discussion, and prayer.'),
    LEADERSHIP: _('The gift of orchestrating the gifts and resources of others to accomplish the work of God. Leaders move people toward a God-given vision of service, and they enable others to use their gifts to the best of their abilities. Leaders are capable of creating synergy, whereby a group achieves much more than its individual members could achieve on their own.'),
    MIRACLES: _('The gift of an ability to operate at a spiritual level that recognizes the miraculous work of God in the world. Miracle workers invoke God’s power to accomplish that which appears impossible or impractical by worldly standards. Miracle workers remind us of the extraordinary nature of the ordinary world, thereby increasing faithfulness and trust in God. Miracle workers pray for God to work in the lives of others, and they feel no sense of surprise when their prayers are answered.'),
    PROPHECY: _('The gift of speaking the word of God clearly and faithfully. Prophets allow God to speak through them to communicate the message that people most need to hear. While often unpopular, prophets are able to say what needs to be said because of the spiritual empowerment they receive. Prophets do not foretell the future, but they proclaim God’s future by revealing God’s perspective on our current reality.'),
    SERVANTHOOD: _('The gift of serving the spiritual and material needs of other people. Servants understand their role in the body of Christ to be that of giving comfort and aid to all who are in need. Servants look to the needs of others rather than focusing on their own needs. To serve is to put faith into action; it is to treat others as if they were Jesus Christ. The gift of service extends our Christian love into the world.'),
    SHEPHERDING: _('The gift of guidance. Shepherds nurture others in the Christian faith and provide a mentoring relationship to those who are new to the faith. Displaying an unusual spiritual maturity, shepherds share from their experience and learning to facilitate the spiritual growth and development of others. Shepherds take individuals under their care and walk with them on their spiritual journeys. Many shepherds provide spiritual direction and guidance to a wide variety of believers.'),
    TEACHING: _('The gift of bringing scriptural and spiritual truths to others. More than just teaching Christian education classes, teachers witness to the truth of Jesus Christ in a variety of ways, and they help others to understand the complex realities of the Christian faith. Teachers are revealers. They shine the light of understanding into the darkness of doubt and ignorance. They open people to new truths, and they challenge people to be more in the future than they have been in the past.'),
    TONGUES: _('The gift of (1) the ability to communicate the gospel to other people in a foreign language without the benefit of having studied said language or (2) the ability to speak to God in a secret, unknown prayer language that can only be understood by a person possessing the gift of interpretation. The ability to speak in the language of another culture makes the gift of tongues valuable for spreading the gospel throughout the world, while the gift of speaking a secret prayer language offers the opportunity to build faithfulness within a community of faith.'),
    WISDOM: _('The gift of translating life experience into spiritual truth and of seeing the application of scriptural truth to daily living. The wise in our faith communities offer balance and understanding that transcend reason. Wisdom applies a God-given common sense to our understanding of God’s will. Wisdom helps us remain focused on the important work of God, and it enables newer, less mature Christians to benefit from those who have been blessed by God to share deep truths.'),
}

# Gift Languages -------------------------------------------------------
ENGLISH = 'en'
PERSIAN = 'fa'
TURKISH = 'tr'
SPANISH = 'es'
CHINESE = 'zh'
ARABIC = 'ar'
KOREAN = 'ko'
FRENCH = 'fr'
GERMAN = 'de'
ITALIAN = 'it'
PORTUGUESE = 'pt'
RUSSIAN = 'ru'
JAPANESE = 'ja'
HINDI = 'hi'
BENGALI = 'bn'
URDU = 'ur'
INDONESIAN = 'id'
TAMIL = 'ta'
MALAY = 'ms'
VIETNAMESE = 'vi'
THAI = 'th'

GIFT_LANGUAGE_CHOICES = [
    (ENGLISH, _('English')),
    (PERSIAN, _('Persian')),
    (TURKISH, _('Turkish')),
    (SPANISH, _('Spanish')),
    (CHINESE, _('Chinese')),
    (ARABIC, _('Arabic')),
    (KOREAN, _('Korean')),
    (FRENCH, _('French')),
    (GERMAN, _('German')),
    (ITALIAN, _('Italian')),
    (PORTUGUESE, _('Portuguese')),
    (RUSSIAN, _('Russian')),
    (JAPANESE, _('Japanese')),
    (HINDI, _('Hindi')),
    (BENGALI, _('Bengali')),
    (URDU, _('Urdu')),
    (INDONESIAN, _('Indonesian')),
    (TAMIL, _('Tamil')),
    (MALAY, _('Malay')),
    (VIETNAMESE, _('Vietnamese')),
    (THAI, _('Thai')),
]


# Answer Gifts --------------------------------------------------
ANSWER_CHOICES = [
    (1, '1'),
    (2, '2'),
    (3, '3'),
    (4, '4'),
    (5, '5'),
    (6, '6'),
    (7, '7'),
]


# Answers in 21 languages ----------------------------------------
GIFT_ANSWER_LABELS = {
    "en": {
        7: "Always",
        6: "Almost Always",
        5: "Often",
        4: "Sometimes",
        3: "Rarely",
        2: "Almost Never",
        1: "Never",
    },
    "fa": {
        7: "همیشه",
        6: "تقریباً همیشه",
        5: "اغلب",
        4: "گاهی اوقات",
        3: "به ندرت",
        2: "تقریباً هرگز",
        1: "هرگز",
    },
    "ar": {
        7: "دائمًا",
        6: "تقريبًا دائمًا",
        5: "غالبًا",
        4: "أحيانًا",
        3: "نادراً",
        2: "تقريبًا أبدًا",
        1: "أبدًا",
    },
    "fr": {
        7: "Toujours",
        6: "Presque toujours",
        5: "Souvent",
        4: "Parfois",
        3: "Rarement",
        2: "Presque jamais",
        1: "Jamais",
    },
    "es": {
        7: "Siempre",
        6: "Casi siempre",
        5: "A menudo",
        4: "A veces",
        3: "Raramente",
        2: "Casi nunca",
        1: "Nunca",
    },
    "de": {
        7: "Immer",
        6: "Fast immer",
        5: "Oft",
        4: "Manchmal",
        3: "Selten",
        2: "Fast nie",
        1: "Nie",
    },
        "tr": {
        7: "Her zaman",
        6: "Neredeyse her zaman",
        5: "Sıklıkla",
        4: "Bazen",
        3: "Nadiren",
        2: "Neredeyse hiç",
        1: "Hiçbir zaman",
    },
        "zh": {
        7: "总是",
        6: "几乎总是",
        5: "经常",
        4: "有时",
        3: "很少",
        2: "几乎从不",
        1: "从不",
    },
        "ko": {
        7: "항상",
        6: "거의 항상",
        5: "자주",
        4: "가끔",
        3: "드물게",
        2: "거의 안 함",
        1: "전혀 안 함",
    },"ja": {
        7: "いつも",
        6: "ほとんどいつも",
        5: "よくある",
        4: "時々",
        3: "めったにない",
        2: "ほとんどない",
        1: "全くない",
    },
    "ru": {
        7: "Всегда",
        6: "Почти всегда",
        5: "Часто",
        4: "Иногда",
        3: "Редко",
        2: "Почти никогда",
        1: "Никогда",
    },
    "it": {
        7: "Sempre",
        6: "Quasi sempre",
        5: "Spesso",
        4: "A volte",
        3: "Raramente",
        2: "Quasi mai",
        1: "Mai",
    },
    "pt": {
        7: "Sempre",
        6: "Quase sempre",
        5: "Frequentemente",
        4: "Às vezes",
        3: "Raramente",
        2: "Quase nunca",
        1: "Nunca",
    },
    "hi": {
        7: "हमेशा",
        6: "लगभग हमेशा",
        5: "अक्सर",
        4: "कभी-कभी",
        3: "कभी-कभी ही",
        2: "लगभग कभी नहीं",
        1: "कभी नहीं",
    },
    "bn": {
        7: "সবসময়",
        6: "প্রায় সবসময়",
        5: "প্রায়ই",
        4: "মাঝে মাঝে",
        3: "কদাচিৎ",
        2: "প্রায় কখনো না",
        1: "কখনো না",
    },
    "ur": {
        7: "ہمیشہ",
        6: "تقریباً ہمیشہ",
        5: "اکثر",
        4: "کبھی کبھی",
        3: "شاذ و نادر",
        2: "تقریباً کبھی نہیں",
        1: "کبھی نہیں",
    },
    "id": {
        7: "Selalu",
        6: "Hampir selalu",
        5: "Sering",
        4: "Kadang-kadang",
        3: "Jarang",
        2: "Hampir tidak pernah",
        1: "Tidak pernah",
    },
    "ta": {
        7: "எப்போதும்",
        6: "கிட்டத்தட்ட எப்போதும்",
        5: "அடிக்கடி",
        4: "சில நேரங்களில்",
        3: "அவசரமாக",
        2: "தீவிரமல்லாத",
        1: "ஒருபோதும் இல்லை",
    },
    "ms": {
        7: "Sentiasa",
        6: "Hampir sentiasa",
        5: "Selalu",
        4: "Kadang-kadang",
        3: "Jarang",
        2: "Hampir tidak pernah",
        1: "Tidak pernah",
    },
    "vi": {
        7: "Luôn luôn",
        6: "Gần như luôn luôn",
        5: "Thường xuyên",
        4: "Đôi khi",
        3: "Hiếm khi",
        2: "Hầu như không bao giờ",
        1: "Không bao giờ",
    },
    "th": {
        7: "เสมอ",
        6: "เกือบเสมอ",
        5: "บ่อยครั้ง",
        4: "บางครั้ง",
        3: "ไม่ค่อย",
        2: "แทบไม่เคย",
        1: "ไม่เคย",
    }
}


