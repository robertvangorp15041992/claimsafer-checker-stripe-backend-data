import asyncio
import logging
from app.metrics import increment_email_sent

logger = logging.getLogger("app.background")

class BackgroundQueue:
    def __init__(self):
        self.loop = asyncio.get_event_loop()
        self.tasks = []

    def enqueue(self, func, *args, retry=3, backoff_sec=2, **kwargs):
        task = self.loop.create_task(self._run_with_retry(func, *args, retry=retry, backoff_sec=backoff_sec, **kwargs))
        self.tasks.append(task)
        return task

    async def _run_with_retry(self, func, *args, retry=3, backoff_sec=2, **kwargs):
        for attempt in range(retry):
            try:
                await func(*args, **kwargs)
                return
            except Exception as e:
                logger.error(f"Background task failed: {e}, attempt {attempt+1}")
                await asyncio.sleep(backoff_sec * (2 ** attempt))
        logger.error("Background task failed after retries.")

queue = BackgroundQueue()

async def send_email_bg(to, subject, html, text=None, template="generic"):
    from app.utils import send_email
    send_email(to, subject, html, text)
    increment_email_sent(template)

async def post_payment_bg(user_id):
    # Placeholder for post-payment async work
    pass
