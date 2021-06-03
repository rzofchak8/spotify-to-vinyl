## Current plan for future changes
---

1. self rate-limit because discogs api is very slow (60 requests per min), may need to rate-limit spotify api queries as well
 - usable after this
 *note*: spotify status code 429 - perhaps query and wait if need be...  discogs, timeout requests per each second

2. transform to observer pattern so we only update on playlist change detected (is this possible?)

3. host backend essentially for query request, in order to hide the consumer keys
 - would signify the completion of initial idea

4. (optional) multi-playlist tracking?

pivoting...
5. one-off webapp option instead of background process, essentially what this is leading towards

...
6. expand to multiple streaming platforms if realistic
 - would require refactoring of code, not like it needs it already
---
