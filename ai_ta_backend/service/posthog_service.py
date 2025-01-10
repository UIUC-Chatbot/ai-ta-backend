import os

from injector import inject
from posthog import Posthog


class PosthogService:

  @inject
  def __init__(self):
    if os.getenv("POSTHOG_API_KEY"):
      self.posthog = Posthog(
          sync_mode=False,
          project_api_key=os.getenv("POSTHOG_API_KEY", None),
          host="https://app.posthog.com",
      )
    else: 
      self.posthog = None

  def capture(self, event_name, properties):
    if self.posthog:
      self.posthog.capture("distinct_id_of_the_user", event=event_name, properties=properties)
