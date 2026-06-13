# INFRASTRUCTURE

import sys
from collections import deque
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from p1_fetch import fetch_url
from p2_cooldown import CooldownManager
from p5_logger import AcquireLogger


# ORCHESTRATOR

def run_loop(
    candidates: list[tuple[str, str]],
    target_urls: list[str],
    content_type: str,
    logger: AcquireLogger,
) -> tuple[list[str], list[str]]:
    """Target-driven fetch-with-rotation loop. Return (done_urls, gap_urls).

    done_urls: target URLs successfully fetched.
    gap_urls:  URLs still pending when all candidates are on cooldown.
    Every request is a productive fetch — no separate proxy-check stage.
    """
    queue   = deque(target_urls)
    done: list[str] = []
    cm      = CooldownManager()

    rider: tuple[str, str] | None = None  # (proto, host_port) currently being ridden
    rider_b = 0                            # successful fetches delivered by current rider

    while queue:
        # Elect rider: keep current if still eligible, else pick next candidate
        if rider is None or not cm.is_eligible(*rider):
            eligible = cm.eligible_candidates(candidates)
            if not eligible:
                break   # all candidates on cooldown → gap
            rider   = eligible[0]   # socks4-first already sorted by CooldownManager
            rider_b = 0

        url          = queue[0]     # peek — only pop on success
        proto, hp    = rider
        ok, _content = fetch_url(proto, hp, url, content_type)

        logger.record_attempt(proto, hp, url, ok)

        if ok:
            queue.popleft()
            done.append(url)
            rider_b += 1
            # keep riding — rider unchanged
        else:
            # URL stays at front of queue for next candidate
            logger.record_burn(proto, hp, b_count=rider_b)
            cm.mark_burned(proto, hp)
            rider   = None
            rider_b = 0

        # Snapshot eligible-pool size AFTER the action (captures burn shrinkage)
        logger.record_working_set(len(cm.eligible_candidates(candidates)))

    gap = list(queue)
    return done, gap
