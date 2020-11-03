from base.module import ModuleBase
from base.events import EVT_STREAM_STATUS
from lib.common import get_broadcaster

class LiveNotificationModule(ModuleBase):
	module_name = 'live_notification'
	def setup(self):
		self.event_listen(EVT_STREAM_STATUS, self.status_change)

	def status_change(self, event):
		if event.is_live:
			broadcaster = get_broadcaster()
			if event.live_time < 600:
				self.send_chat_message(f'{broadcaster.display_name} is LIVE!')
				self.send_chat_message(event.title)
