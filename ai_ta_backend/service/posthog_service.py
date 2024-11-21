import os

from injector import inject
from posthog import Posthog


class PosthogService:

  @inject
  def __init__(self):
    if not os.getenv("POSTHOG_API_KEY"):
      self.posthog = None
      return

    self.posthog = Posthog(
        sync_mode=True,
        project_api_key=os.environ["POSTHOG_API_KEY"],
        host="https://app.posthog.com",
    )

  def capture(self, event_name, properties):
    if not self.posthog:
      return

    self.posthog.capture("distinct_id_of_the_user", event=event_name, properties=properties)
