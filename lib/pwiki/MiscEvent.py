# TODO Weak references!

import weakref


class MiscEventSourceMixin:
    """
    Mixin class to handle misc events
    """
    def __init__(self):
        self._MiscEventSourceMixin__miscevent = None


    def getMiscEvent(self):
        if (not hasattr(self, "_MiscEventSourceMixin__miscevent")) or \
                (not self._MiscEventSourceMixin__miscevent):
            self._MiscEventSourceMixin__miscevent = MiscEvent(self)
            
        return self._MiscEventSourceMixin__miscevent


    def removeMiscEvent(self):
        if hasattr(self, "_MiscEventSourceMixin__miscevent"):
            del self._MiscEventSourceMixin__miscevent


    def fireMiscEventProps(self, props, first=None):
        """
        props -- Dictionary {key: value} with properties
        first -- first object to call its miscEventHappened method
                 before other listeners are processed or None
                 
        return:  create clone event
        """
        return self.getMiscEvent().createCloneAddProps(props).processSend(first)


    def fireMiscEventKeys(self, keys, first=None):
        """
        keys -- Sequence with key strings
        first -- first object to call its miscEventHappened method
                 before other listeners are processed or None

        return:  create clone event
        """
        return self.getMiscEvent().createCloneAddKeys(keys).processSend(first)



class ListenerList(object):
    __slots__ = ("__weakref__", "listeners", "userCount", "cleanupFlag")

    def __init__(self):
        self.listeners = []
        self.userCount = 0
        self.cleanupFlag = False
        
    def addListener(self, listener, isWeak=True):
        """
        isWeak -- Iff true, store weak reference to listener instead
                of listener itself
        """
        if isWeak:
            self.listeners.append(weakref.ref(listener))
        else:
            self.listeners.append(listener)

    def removeListener(self, listener):
        try:
            self.listeners.remove(weakref.ref(listener))
        except ValueError:
            try:
                self.listeners.remove(listener)
            except ValueError:
                # Wasn't in the list
                pass
                
    def hasListener(self, listener):
        try:
            self.listeners.index(weakref.ref(listener))
            return True
        except ValueError:
            try:
                self.listeners.index(listener)
                return True
            except ValueError:
                return False


    def setListeners(self, listeners):
        self.listeners = listeners
        
    def incListenerUser(self):
        self.userCount += 1
        return self.listeners
        
    def decListenerUser(self):
        if self.userCount > 0:
            self.userCount -= 1
            
            if self.userCount == 0 and self.cleanupFlag:
                self.cleanDeadRefs()
                self.cleanupFlag = False


    def setCleanupFlag(self, value=True):
        self.cleanupFlag = value


    def getActualObject(lref):
        if lref is None:
            return None

        if isinstance(lref, weakref.ReferenceType):
            return lref()  # Retrieve real object from weakref object
    getActualObject = staticmethod(getActualObject)


    def getObjectAt(self, i):
        lref = self.listeners[i]
        if lref is None:
            self.cleanupFlag = True
            return None

        if isinstance(lref, weakref.ReferenceType):
            l = lref()
            if l is None:
                self.cleanupFlag = True
                return None
        else:
            l = lref
            
        return l  # Return real


    def cleanDeadRefs(self):
        """
        Remove references to already deleted objects.
        """
        i = 0
        while i < len(self.listeners):
            if self.getActualObject(self.listeners[i]) is None:
                del self.listeners[i]
                continue # Do not increment i here

            i += 1
            
    def __len__(self):
        return len(self.listeners)




class MiscEvent(object):
    __slots__ = ("__weakref__", "listenerList", "source", "properties", "parent",
            "activeListenerIndex")

    def __init__(self, source = None):
        self.listenerList = ListenerList()
        self.source = source
        self.properties = None
        self.parent = None
        
        # Index into self.listeners which listener is currently called
        # needed for noChildrenForMe().
        self.activeListenerIndex = -1

    def getSource(self):
        return self.source

    def setSource(self, source):
        self.source = source

    def get(self, key, default = None):
        """
        Return value for specified key or default if not found.
        Be careful: The value itself may be None.
        """
        return self.properties.get(key, default)

    def has_key(self, key):
        """
        Has the event the specified key?
        """
        return self.properties.has_key(key)

    def has_key_in(self, keyseq):
        """
        Returns true iff it has at least one key in the sequence of keys keyseq
        """
        for key in keyseq:
            if self.has_key(key):
                return True
                
        return False

    def getParent(self):
        """
        The MiscEvent which was called to fire this clone. If it returns null this is not a clone.
        """
        return self.parent

    def clone(self):
        """
        Normally you shouldn't call this method directly,
        call createClone() instead
        """
        result = MiscEvent()

        result.listenerList = self.listenerList
        
        if self.properties is not None:
            result.properties = self.properties.copy()

        return result


    # A MiscEvent manages the listener list itself.

    def addListener(self, listener, isWeak=True):
        """
        isWeak -- Iff true, store weak reference to listener instead
                of listener itself
        """
        return self.listenerList.addListener(listener, isWeak)

    def removeListener(self, listener):
        return self.listenerList.removeListener(listener)
                
    def hasListener(self, listener):
        return self.listenerList.hasListener(listener)

    def setListeners(self, listeners):
        return self.listenerList.setListeners(listeners)

    def setListenerList(self, listenerList):
        self.listenerList = listenerList

    def put(self, key, value = None):
        """
        Add a key-value pair to the internal Hashtable.
        <B>Can't be called on an original MiscEvent, must be a clone.</B>

        @return  this, so you can chain the call: event = event.put("a", a).put("foo", bar);

        @throws NullPointerException       if key is null
        @throws IllegalArgumentException   if this is not a clone
        """
        if self.getParent() is None:
            raise StandardError("This must be a clone")  # TODO Create/Find a better exception

        self.properties[key] = value
        return self
        
        
    def cleanDeadRefs(self):
        """
        Remove references to already deleted objects. Mainly called by processSend
        to clean the parent event if a child finds a deadref.
        
        """
##        Automatically calls cleanDeadRefs of its parent event (if existing).
        self.listenerList.cleanDeadRefs()

#         parent = self.getParent()
#         if parent is not None:
#             parent.cleanDeadRefs()


    def processSend(self, first = None):
        """
        Called on the clone to dispatch itself to first, then to all listeners.
        <B>Can't be called on an original MiscEvent, must be a clone.</B>

        @param first   the first listener the event dispatches before dispatching to remaining listeners. A null value is ignored.
        @throws IllegalArgumentException   if this is not a clone
        """
        if self.getParent() is None:
            raise StandardError("This must be a clone")  # TODO Create/Find a better exception

        if first is not None:
            first.miscEventHappened(self);
        
        self.listenerList.incListenerUser()
        try:
            i = 0
            while i < len(self.listenerList):
                l = self.listenerList.getObjectAt(i)
                if l is None:
                    continue
                
                self.activeListenerIndex = i
                l.miscEventHappened(self)
                
                i += 1

        finally:
            self.listenerList.decListenerUser()

        self.activeListenerIndex = -1

        return self
            
            
    def createClone(self):
        """
        Creates a clone with the appropriate data, so dispatching can be done later.<BR>
        Some methods can be called only on a cloned MiscEvent.
        To add properties, use the put() method.

        _source -- The object which will dispatch the event
        """
        event = self.clone()
        if event.properties is None:
            event.properties = {}

        event.source = self.source
        event.parent = self

        return event
        
    def getProps(self):
        """
        Return properties dictionary. The returned dictionary should not
        be altered.
        """
        return self.properties


    def addProps(self, addprops):
        """
        Add/update properties of the event

        @param addprops  Dictionary with additional properties
        @return self
        """
        self.properties.update(addprops)
        return self


    def addKeys(self, addkeys):
        """
        Add/update keys of the event

        @param addkeys  Sequence with additional keys for properties
        @return self
        """
        for k in addkeys:
            self.properties[k] = True
        return self
        

    def createCloneAddProps(self, addprops):
        """
        Creates a clone with the appropriate data, so dispatching can be done later.<BR>
        Some methods can be called only on a cloned MiscEvent.

        @param addprops  Dictionary with additional properties
        """
        event = self.createClone()
        event.properties.update(addprops)
        return event

    def createCloneAddKeys(self, addkeys):
        """
        Creates a clone with the appropriate data, so dispatching can be done later.<BR>
        Some methods can be called only on a cloned MiscEvent.

        @param addkeys  Sequence with additional keys for properties
        """
        event = self.createClone()
        for k in addkeys:
            event.properties[k] = True
        return event


#     def noChildrenForMe():
#         """
#         Called by a listener to ensure that it doesn't get any child events
#         of this event
#         """
#         if self.activeListenerIndex == -1:
#             # TODO Create/Find a better exception
#             raise StandardError("Must be called during processing of an event")
#             
#         self.listeners[self.activeListenerIndex] = None



class ResendingMiscEvent(MiscEvent):
    """
    This specialized MiscEvent registers as listener to a list of other
    MiscEvents and resends any events send by them. When sending, source is
    changed to the ResendingEvent (the parent, not the clone).
    """
    __slots__ = ("watchedEvents",)
    
    def __init__(self, source=None):
        MiscEvent.__init__(self, source)
        self.watchedEvents = []
    
    def setWatchedEvents(self, watchedEvents):
        if watchedEvents is None:
            watchedEvents = []

        for ev in self.watchedEvents:
            ev.removeListener(self)
        
        self.watchedEvents = watchedEvents
        
        for ev in self.watchedEvents:
            ev.addListener(self)
        
    def getWatchedEvents(self):
        return self.watchedEvents
        
    def miscEventHappened(self, miscevt):
        newMiscevt = miscevt.createClone()
        newMiscevt.setSource(self)
        newMiscevt.setListenerList(self.listenerList)
        newMiscevt.processSend()



class KeyFunctionSink(object):
    """
    A MiscEvent sink which dispatches events further to other functions
    """
    __slots__ = ("__weakref__", "activationTable")
    
    def __init__(self, activationTable):
        """
        activationTable -- Sequence of tuples (<key in props>, <function to call>)
        """
        self.activationTable = activationTable
    
    def miscEventHappened(self, evt):
        for k, f in self.activationTable:
            if evt.has_key(k):
                f(evt)


class DebugSimple(object):
    """
    A MiscEvent sink which dispatches events further to other functions
    """
    __slots__ = ("__weakref__", "text")
    
    def __init__(self, text):
        """
        """
        self.text = text
    
    def miscEventHappened(self, evt):
        print self.text, repr(evt.properties)


