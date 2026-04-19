# Welcome to the Jungle uses a public Algolia search API.
# These keys are surfaced in the site's frontend JavaScript and are intended for
# client-side search. They are hardcoded here per the project's chosen strategy
# (Option B). If the public key rotates, the scraper will fail with a clear
# WelcomeToTheJungleException; update the values below to recover.
#
# Source of truth: inspect window.__INITIAL_STATE__ / Apollo client config on
# https://www.welcometothejungle.com/en/jobs (network panel: any algolia.net call).

ALGOLIA_APP_ID = "CSEKHVMS53"
ALGOLIA_API_KEY = "1f1119b8081b6890f6cdef7df37c3a2c"  # public search-only key
ALGOLIA_INDEX = "wk_jobs_en_jobs"

algolia_headers = {
    "accept": "*/*",
    "accept-language": "en-US,en;q=0.9",
    "content-type": "application/x-www-form-urlencoded",
    "origin": "https://www.welcometothejungle.com",
    "referer": "https://www.welcometothejungle.com/",
    "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36",
}

site_headers = {
    "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "accept-language": "en-US,en;q=0.9",
    "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36",
}
