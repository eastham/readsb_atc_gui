from kivmd.app import MDApp
from kivymd.uix.floatlayout import MDFloatLayout
from kivymd.uix.dialog import MDDialog
from kivymd.uix.button import MDFlatButton, MDRaisedButtom
from kivy.lang.builder impor Builder
from kivy.toast import toast


kv = '''
MDBoxLayout:
    orientation : 'vertical'

    MDFlatbutton:
        text : 'Dialog'
        pos_hint : {'center_x':.5'}
        on_release : app.show_custom_dialog()

<Content>:
    MDTextField:
        id : pin
        pos_hint : {'center_x':.5,'center_y':.5}

'''

class Content(MDFloatLayout):
    pass


class InputDialogApp(MDApp):
    cdialog = None

    def build(self):
        return Builder.load_string(kv)

    def show_custom_dialog(self):
        content_cls = Content()
        self.cdialog = MDDialog(title='Enter Pin',
                 content_cls=content_cls,
                type='custom')
        self.cdialog.buttons = [

                MDFlatButton(text="Cancel",on_release=self.close_dialog),

               MDRaisedButton(text="Ok",on_release=lambda x:self.get_data(x,content_cls))
                ]
        self.cdialog.open()

    def close_dialog(self, instance):
        if self.cdialog:
            self.cdialog.dismiss()

    def get_data(self, instance_btn, content_cls):
        textfield = content_cls.ids.pin
        value = textfield._get_text()
        # do stuffs here
        toast(value)

        self.close_dialog(instance_btn)

if __name__ == '__main__':
    InputDialogApp().run()
