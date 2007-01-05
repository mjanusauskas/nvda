import time
import ctypes
import debug
import core
import winUser
import IAccessibleHandler
import audio
import api
import config
import NVDAObjects
from baseType import *

NAVRELATION_EMBEDS=0x1009 

class virtualBuffer_gecko(virtualBuffer):

	def __init__(self,NVDAObject):
		virtualBuffer.__init__(self,NVDAObject)
		#(pacc,child)=IAccessibleHandler.accessibleObjectFromEvent(self.NVDAObject.windowHandle,0,0)
		#(pacc,child)=IAccessibleHandler.accNavigate(pacc,child,NAVRELATION_EMBEDS)
		#self.NVDAObject=NVDAObjects.IAccessible.NVDAObject_IAccessible(pacc,child)
		audio.speakMessage("gecko virtualBuffer %s %s"%(self.NVDAObject.name,self.NVDAObject.typeString))
		if self.isDocumentComplete():
			self.loadDocument()

	def event_IAccessible_gainFocus(self,hwnd,objectID,childID):
		obj=NVDAObjects.IAccessible.getNVDAObjectFromEvent(hwnd,objectID,childID)
		if not obj:
			return False
		role=obj.role
		states=obj.states
		if (role==IAccessibleHandler.ROLE_SYSTEM_DOCUMENT) and (states&IAccessibleHandler.STATE_SYSTEM_READONLY):
			if (states&IAccessibleHandler.STATE_SYSTEM_BUSY):
				audio.speakMessage(IAccessibleHandler.getStateName(IAccessibleHandler.STATE_SYSTEM_BUSY))
			elif self.getNVDAObjectID(obj)!=self.getNVDAObjectID(self.NVDAObject): 
				self.NVDAObject=obj
				self.loadDocument()
			return True
		if (role not in [IAccessibleHandler.ROLE_SYSTEM_TEXT,IAccessibleHandler.ROLE_SYSTEM_CHECKBUTTON,IAccessibleHandler.ROLE_SYSTEM_RADIOBUTTON,IAccessibleHandler.ROLE_SYSTEM_COMBOBOX,IAccessibleHandler.ROLE_SYSTEM_PUSHBUTTON]) and api.isVirtualBufferPassThrough():
  			api.toggleVirtualBufferPassThrough()
		if not self._allowCaretMovement:
			return False
		ID=self.getNVDAObjectID(obj)
		r=self.getRangeFromID(ID)
		if (r is not None) and (len(r)==2) and ((self.caretPosition<r[0]) or (self.caretPosition>=r[1])):
			self.caretPosition=r[0]
			if config.conf["virtualBuffers"]["reportVirtualPresentationOnFocusChanges"]:
				self.reportCaretIDMessages()
				audio.speakText(self.getTextRange(r[0],r[1]))
				api.setFocusObject(obj)
				api.setNavigatorObject(obj)
				return True
		return False

	def event_IAccessible_scrollingStart(self,hwnd,objectID,childID):
		audio.speakMessage("scroll")
		obj=NVDAObjects.IAccessible.getNVDAObjectFromEvent(hwnd,objectID,childID)
		if not obj:
			return False
		if not self._allowCaretMovement:
			return False
		ID=self.getNVDAObjectID(obj)
		audio.speakMessage("ID: %s, obj: %s"%(ID,obj.role))
		r=self.getRangeFromID(ID)
		if (r is not None) and (len(r)==2) and ((self.caretPosition<r[0]) or (self.caretPosition>=r[1])):
			self.caretPosition=r[0]
			self.reportCaretIDMessages()
			audio.speakText(self.getTextRange(r[0],r[1]))

	def event_IAccessible_stateChange(self,hwnd,objectID,childID):
		obj=NVDAObjects.IAccessible.getNVDAObjectFromEvent(hwnd,objectID,childID)
		role=obj.role
		states=obj.states
		if (role==IAccessibleHandler.ROLE_SYSTEM_DOCUMENT) and (states&IAccessibleHandler.STATE_SYSTEM_READONLY):
			if states&IAccessibleHandler.STATE_SYSTEM_BUSY:
				audio.speakMessage(IAccessibleHandler.getStateName(IAccessibleHandler.STATE_SYSTEM_BUSY))
				return True
			elif self.getNVDAObjectID(obj)!=self.getNVDAObjectID(self.NVDAObject):
				self.NVDAObject=obj
				self.loadDocument()
				return True
		return False

	def event_IAccessible_valueChange(self,hwnd,objectID,childID):
		audio.speakMessage('value')
		return False

	def activatePosition(self,pos):
		IDs=self.getIDsFromPosition(pos)
		if (IDs is None) or (len(IDs)<1):
			return
		obj=self._IDs[IDs[-1]]["node"]
		if obj is None:
			return
		role=obj.role
		if role in [IAccessibleHandler.ROLE_SYSTEM_TEXT,IAccessibleHandler.ROLE_SYSTEM_COMBOBOX]:
			if not api.isVirtualBufferPassThrough():
				api.toggleVirtualBufferPassThrough()
			obj.setFocus()
		if role in [IAccessibleHandler.ROLE_SYSTEM_CHECKBUTTON,IAccessibleHandler.ROLE_SYSTEM_RADIOBUTTON]:
			obj.doDefaultAction()
		elif role==IAccessibleHandler.ROLE_SYSTEM_PUSHBUTTON:
			obj.doDefaultAction()
		elif role in [IAccessibleHandler.ROLE_SYSTEM_LINK,IAccessibleHandler.ROLE_SYSTEM_GRAPHIC]:
			obj.doDefaultAction()
			obj.setFocus()

	def isDocumentComplete(self):
		role=self.NVDAObject.role
		states=self.NVDAObject.states
		if (role==IAccessibleHandler.ROLE_SYSTEM_DOCUMENT) and not (states&IAccessibleHandler.STATE_SYSTEM_BUSY) and (states&IAccessibleHandler.STATE_SYSTEM_READONLY):
			return True
		else:
			return False

	def loadDocument(self):
		if winUser.getAncestor(self.NVDAObject.windowHandle,winUser.GA_ROOT)==winUser.getForegroundWindow():
			audio.cancel()
			if api.isVirtualBufferPassThrough():
				api.toggleVirtualBufferPassThrough()
			audio.speakMessage(_("loading document %s")%self.NVDAObject.name+"...")
		self.resetBuffer()
		debug.writeMessage("virtualBuffers.gecko.fillBuffer: load start") 
		self.fillBuffer(self.NVDAObject)
		debug.writeMessage("virtualBuffers.gecko.fillBuffer: load end")
		self.caretPosition=0
		if winUser.getAncestor(self.NVDAObject.windowHandle,winUser.GA_ROOT)==winUser.getForegroundWindow():
			audio.cancel()
			self.caretPosition=0
			self._allowCaretMovement=False #sayAllGenerator will set this back to true when done
			time.sleep(0.01)
			audio.speakMessage(_("done"))
			core.newThread(self.sayAllGenerator())

	def fillBuffer(self,obj,IDAncestors=(),position=None):
		role=obj.role
		states=obj.states
		text=""
		#Get the info and text depending on the node type
		info=fieldInfo.copy()
		info["node"]=obj
		if role==IAccessibleHandler.ROLE_SYSTEM_STATICTEXT:
			data=obj.value
			if data and not data.isspace():
				text="%s "%data
		elif role=="white space":
			text=obj.name.replace('\r\n','\n')
		elif role=="frame":
			info["fieldType"]=fieldType_frame
			info["typeString"]=fieldNames[fieldType_frame]
		if role=="iframe":
			info["fieldType"]=fieldType_frame
			info["typeString"]=fieldNames[fieldType_frame]
		elif role==IAccessibleHandler.ROLE_SYSTEM_DOCUMENT:
			text="%s\n "%obj.name
			info["fieldType"]=fieldType_document
			info["typeString"]=fieldNames[fieldType_document]
		elif role==IAccessibleHandler.ROLE_SYSTEM_LINK:
			info["fieldType"]=fieldType_link
			info["typeString"]=obj.typeString
		elif role=="p":
			info["fieldType"]=fieldType_paragraph
			info["typeString"]=fieldNames[fieldType_paragraph]
		elif role==IAccessibleHandler.ROLE_SYSTEM_CELL:
			info["fieldType"]=fieldType_cell
			info["typeString"]=fieldNames[fieldType_cell]
		elif role==IAccessibleHandler.ROLE_SYSTEM_TABLE:
			info["fieldType"]=fieldType_table
			info["typeString"]=fieldNames[fieldType_table]
		elif role==IAccessibleHandler.ROLE_SYSTEM_ROW:
			info["fieldType"]=fieldType_row
			info["typeString"]=fieldNames[fieldType_row]
		elif role=="thead":
			info["fieldType"]=fieldType_tableHeader
			info["typeString"]=fieldNames[fieldType_tableHeader]
		elif role=="tfoot":
			info["fieldType"]=fieldType_tableFooter
			info["typeString"]=fieldNames[fieldType_tableFooter]
		elif role=="tbody":
			info["fieldType"]=fieldType_tableBody
			info["typeString"]=fieldNames[fieldType_tableBody]
		elif role==IAccessibleHandler.ROLE_SYSTEM_LIST:
			info["fieldType"]=fieldType_list
			info["typeString"]=fieldNames[fieldType_list]
			info["descriptionFunc"]=lambda x: "with %s items"%x.childCount
		elif role==IAccessibleHandler.ROLE_SYSTEM_LISTITEM:
			info["fieldType"]=fieldType_listItem
			bullet=obj.name.rstrip()
			if not bullet:
				bullet=_("bullet")
			elif bullet.endswith('.'):
				bullet=bullet[0:-1]
			info["typeString"]=bullet
		elif role=="dl":
			info["fieldType"]=fieldType_list
			info["typeString"]=_("definition")+" "+fieldNames[fieldType_list]
			info["descriptionFunc"]=lambda x: _("with %s items")%x.childCount
		elif role=="dt":
			info["fieldType"]=fieldType_listItem
			bullet=obj.name.rstrip()
			if not bullet:
				bullet=_("bullet")
			elif bullet.endswith('.'):
				bullet=bullet[0:-1]
			info["typeString"]=bullet
		elif role=="dd":
			info["fieldType"]=fieldType_listItem
			info["typeString"]=_("definition")
		elif role==IAccessibleHandler.ROLE_SYSTEM_GRAPHIC:
			text="%s "%obj.name
			info["fieldType"]=fieldType_graphic
			info["typeString"]=fieldNames[fieldType_graphic]
		elif role in ["h1","h2","h3","h4","h5","h6"]:
			info["fieldType"]=fieldType_heading
			info["typeString"]=fieldNames[fieldType_heading]+" %s"%role[1]
		elif role=="blockquote":
			info["fieldType"]=fieldType_blockQuote
			info["typeString"]=fieldNames[fieldType_blockQuote]
		elif role=="q":
			info["fieldType"]=fieldType_blockQuote
			info["typeString"]=fieldNames[fieldType_blockQuote]
		elif role==IAccessibleHandler.ROLE_SYSTEM_PUSHBUTTON:
			text="%s "%obj.name
			info["fieldType"]=fieldType_button
			info["typeString"]=fieldNames[fieldType_button]
		elif role=="form":
			info["fieldType"]=fieldType_form
			info["typeString"]=fieldNames[fieldType_form]
		elif role==IAccessibleHandler.ROLE_SYSTEM_RADIOBUTTON:
			text="%s "%obj.name
			info["fieldType"]=fieldType_radioButton
			info["typeString"]=fieldNames[fieldType_radioButton]
			info["stateTextFunc"]=lambda x: IAccessibleHandler.getStateName(IAccessibleHandler.STATE_SYSTEM_CHECKED) if x.states&IAccessibleHandler.STATE_SYSTEM_CHECKED else _("not %s")%IAccessibleHandler.getStateName(IAccessibleHandler.STATE_SYSTEM_CHECKED)
		elif role==IAccessibleHandler.ROLE_SYSTEM_CHECKBUTTON:
			text="%s "%obj.name
			info["fieldType"]=fieldType_checkBox
			info["typeString"]=fieldNames[fieldType_checkBox]
			info["stateTextFunc"]=lambda x: IAccessibleHandler.getStateName(IAccessibleHandler.STATE_SYSTEM_CHECKED) if x.states&IAccessibleHandler.STATE_SYSTEM_CHECKED else _("not %s")%IAccessibleHandler.getStateName(IAccessibleHandler.STATE_SYSTEM_CHECKED)
		elif role==IAccessibleHandler.ROLE_SYSTEM_TEXT:
			text="%s "%obj.value
			info["fieldType"]=fieldType_edit
			info["typeString"]=fieldNames[fieldType_edit]
		elif role==IAccessibleHandler.ROLE_SYSTEM_COMBOBOX:
			text="%s "%obj.value
			info["fieldType"]=fieldType_comboBox
			info["typeString"]=fieldNames[fieldType_comboBox]
		else:
			info["typeString"]=IAccessibleHandler.getRoleName(role) if isinstance(role,int) else role
		accessKey=obj.keyboardShortcut
		if accessKey:
			info["accessKey"]=accessKey
		ID=self.getNVDAObjectID(obj)
		if ID and ID not in IDAncestors:
			IDAncestors=tuple(list(IDAncestors)+[ID])
		if ID and not self._IDs.has_key(ID):
			self.addID(ID,**info)
		if text:
			position=self.addText(IDAncestors,text,position=position)
		#We don't want to render objects inside comboboxes
		if role==IAccessibleHandler.ROLE_SYSTEM_COMBOBOX:
			return position
		#For everything else we keep walking the tree
		func=self.fillBuffer
		for child in obj.children:
			position=func(child,IDAncestors,position=position)
		if role==IAccessibleHandler.ROLE_SYSTEM_DOCUMENT:
			position=self.addText(IDAncestors," ",position)
		return position

	def getNVDAObjectID(self,obj):
		if obj.role!=IAccessibleHandler.ROLE_SYSTEM_STATICTEXT:
			return ctypes.cast(obj._pacc,ctypes.c_void_p).value

