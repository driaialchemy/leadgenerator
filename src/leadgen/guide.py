"""Sidebar usage guide with forgiving keyword search."""

from difflib import SequenceMatcher

TOPICS = (
    ("Getting started", "start begin how first setup",
     "Fill in your details once in settings (name, company, phone, and mailing address). Then on the find page, type your field, pick an industry, and press search."),
    ("Searching for businesses", "find search industry naics look up",
     "Type your occupation or service (for example, social media marketing) and the kind of business you want to reach (for example, restaurants). Pick a suggestion or just press search. The closest industry is used, and you get the 25 best-fit businesses at a time."),
    ("Employee size and areas", "size employees small large city metro phoenix tucson flagstaff",
     "Choose 1–49, 50–99, or 100–250 employees, or leave it empty for any size. Metro areas set where to look: greater Phoenix, greater Tucson, and northern Arizona."),
    ("Show more results", "more next additional page",
     "The show 25 more button adds the next best matches to the same search."),
    ("Previous searches", "previous history earlier past shortlist",
     "When you run a new search, the last results move to previous searches with the date and time. A new search never repeats a business you've already found."),
    ("Seeing old businesses again", "clear previous reset search repeat duplicates",
     "Open previous searches and press clear previous results. Those businesses can then appear in new searches again."),
    ("Writing a draft", "draft write email letter run",
     "On the draft page, pick a business from your current search and press run. To write to someone from an earlier search, choose previous searches, then pick the search date."),
    ("Reviewing a draft", "review read check findings",
     "Read the email. If it lists findings, tick the box to show you've read them. Your name fills in from your details."),
    ("Approve, edit, or reject", "approve edit change wording reject decline",
     "Approve moves the email to the send page as written. To change the wording, open edit the wording, make your changes, and press approve with my edits. Reject drops it."),
    ("Quality score under the bar", "quality score bar warning low",
     "A second AI reads the email as a busy owner would and scores it from 1 to 5 on relevance, specificity, clarity, and tone. A score under 4 means it tried once more and still came up short. It's a warning, not a block. The logbook shows the scores and suggestions."),
    ("Sending", "send gmail outlook practice outbox",
     "Practice saves the email as a file only. Gmail and Outlook save a draft in your mailbox, or send it once you confirm. Connect a mailbox in settings first."),
    ("Your details and signature", "name signature company phone address settings",
     "Your details in settings set how every email is signed. Sending through Gmail or Outlook stays off until they're filled in."),
    ("Starting over", "clear reset start over delete wipe",
     "The clear everything button in the sidebar empties your current search, previous searches, drafts waiting, approvals, and practice sends. Your details, mailbox connections, and the logbook stay."),
    ("Logbook", "log logbook history record audit what happened",
     "A permanent record of every search, draft, check, and decision, with times. It can't be edited or cleared."),
)

HOW_IT_WORKS = {
    "Fill in your details": "Add your name, company, phone, and address once in Settings, and every email is signed with them.",
    "Tell it what you do": "Type your field, such as social media marketing, and the drafts are written from that angle.",
    "Pick who to reach": "Type an industry (it handles misspellings), and choose an employee size and metro areas.",
    "Search": "It scans 50,000 Arizona businesses and shows the 25 best fits, each with an owner, a score, and the reason it fits.",
    "See more or start fresh": "\"Show 25 more\" continues the same search, and a new search never repeats a business you've already found.",
    "Previous searches": "Earlier results are saved by date and time, and \"Clear previous results\" lets those businesses show up again.",
    "Draft": "Pick a business and press Run. One AI picks the angle from the facts on record, another writes the email, and code checks it for made-up claims.",
    "Quality check": "A third AI reads it as a busy owner would and scores it. If the score is low, the email is rewritten once.",
    "Review": "You read it and then approve, edit the wording, or reject. Nothing moves forward without your name on it.",
    "Send": "Save it as a practice file, put it in Gmail or Outlook as a draft, or send it after a confirmation.",
    "Logbook": "Every search, draft, check, and decision is recorded with times, and the record can't be edited.",
    "Clear everything": "One button resets your searches, drafts, approvals, and practice sends. Your details, mailbox connections, and the logbook stay.",
    "Usage guide": "Search the sidebar guide with any word, misspelled or not, for quick help.",
}

CUTOFF = 0.75


def _words(text: str) -> list[str]:
    return [word for word in "".join(c.lower() if c.isalnum() else " " for c in text).split() if word]


def search_guide(query: str, limit: int = 4) -> list[tuple[str, str]]:
    """Topics whose title or keywords match the query, misspellings included. Best first."""
    terms = _words(query)
    if not terms:
        return []
    scored = []
    for index, (title, keywords, answer) in enumerate(TOPICS):
        vocabulary = {word for word in _words(title) + _words(keywords) if len(word) >= 3}
        total = 0.0
        for term in terms:
            best = 0.0
            for word in vocabulary:
                if word.startswith(term) or term.startswith(word):
                    ratio = 1.0 if len(term) >= 3 or term == word else 0.0
                else:
                    ratio = SequenceMatcher(None, term, word).ratio()
                best = max(best, ratio)
            if best >= CUTOFF:
                total += best
        if total:
            scored.append((-total, index, title, answer))
    scored.sort()
    return [(title, answer) for _score, _index, title, answer in scored[:limit]]
