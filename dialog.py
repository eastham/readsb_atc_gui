from kivymd.uix.floatlayout import MDFloatLayout
from kivymd.uix.dialog import MDDialog
from kivymd.uix.button import MDFlatButton, MDRaisedButton
from kivy.lang.builder import Builder
from kivy.uix.boxlayout import BoxLayout

kv = '''
<Content>:
    orientation: "vertical"
    spacing: "12dp"
    size_hint_y: None

    MDTextField:
        id : pin

'''

class Content(BoxLayout):
    pass


class Dialog:
    cdialog = None

    def __init__(self):
        self.app = None
        self.id = None
        Builder.load_string(kv)

    def show_custom_dialog(self, app, id):
        self.app = app
        self.id = id
        content_cls = Content()
        self.cdialog = MDDialog(title='Enter Code', content_cls=content_cls,
            type="custom", buttons = [
                MDFlatButton(text="Cancel",on_release=self.close_dialog),
                MDRaisedButton(text="Ok",on_release=lambda x:self.get_data(x,content_cls))
            ])
        self.cdialog.open()

    def close_dialog(self, instance):
        if self.cdialog:
            self.cdialog.dismiss()

    def get_data(self, instance_btn, content_cls):
        textfield = content_cls.ids.pin
        value = textfield._get_text()
        self.app.annotate_strip(self.id, value)
        self.app.set_strip_color(self.id, (.4,.4,.4))
        self.close_dialog(instance_btn)
