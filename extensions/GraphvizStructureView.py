# Create a graph using Graphviz which shows relations of wiki words
# which are defined by attributes (aka properties).
# 
# Based on code written by josip_ine


import os, os.path, re
from subprocess import list2cmdline

import wx

from pwiki.wxHelper import copyTextToClipboard, GUI_ID


from pwiki.TempFileSet import createTempFile, TempFileSet
from pwiki.StringOps import mbcsEnc, mbcsDec, utf8Enc, lineendToOs, uniToGui, \
        joinRegexes, rgbToHtmlColor, escapeHtmlNoBreaks
from pwiki.AdditionalDialogs import FontFaceDialog
from pwiki.OptionsDialog import PluginOptionsPanel


# descriptor for plugin type(s)

# This plugin is a hybrid and can show the graph either if menu command
# is issued or if insertion is placed
WIKIDPAD_PLUGIN = (("InsertionByKey", 1), ("MenuFunctions", 1), ("Options", 1))



def _buildNodeDefs(wikiDocument, currWord, wordSet=None):
    currWord = wikiDocument.filterAliasesWikiWord(currWord)
    firstDef = u""
    graph = []

    coloredSet = set()

    # define nodes
    for colored_node in wikiDocument.getPropertyTriples(None, 'color', None):
        if not (colored_node[0] == currWord) and not (wordSet is None) and \
                not (colored_node[0] in wordSet):
            continue

        c = wx.NamedColour(colored_node[2].strip())
        
        color_code = rgbToHtmlColor(c.Red(), c.Green(), c.Blue())
        fontColor = u""
        if c.Green() < 128:
            fontColor = u" [fontcolor=white]"
        
        coloredSet.add(colored_node[0])

        if colored_node[0] == currWord:
            firstDef = u'"%s" [fillcolor="%s"]%s' % \
                    (colored_node[0], color_code, fontColor)
        else:
            graph.append(u'"%s" [fillcolor="%s"]%s' %
                    (colored_node[0], color_code, fontColor))
    
    if currWord is not None and firstDef == u"":
        firstDef = u'"%s"' % currWord
#         firstDef = u'"%s" [fillcolor="%s"]' % (currWord, DEFAULT_NODE_BG_COLOR)
        coloredSet.add(currWord)

#     if wordSet is not None:
#         for word in wordSet - coloredSet:
#             graph.append(u'"%s" [fillcolor="%s"]' % (word, DEFAULT_NODE_BG_COLOR))
#     else:
#         for word in wikiDocument.getAllDefinedWikiPageNames():
#             if word in coloredSet:
#                 continue
#             graph.append(u'"%s" [fillcolor="%s"]' % (word, DEFAULT_NODE_BG_COLOR))


    return [firstDef] + graph



def _buildGraphStyle(config):
    nodeStyle = [u'style=filled']

    val = config.get("main", "plugin_graphVizStructure_nodeFacename", u"")
    if val != u"":
        nodeStyle.append(u'fontname="%s"' % val)
    
    val = config.getint("main", "plugin_graphVizStructure_nodeFontsize", 0)
    if val != 0:
        nodeStyle.append(u'fontsize=%s' % val)

    val = config.get("main", "plugin_graphVizStructure_nodeBorderColor", u"")
    if val != u"":
        nodeStyle.append(u'color="%s"' % val)

    val = config.get("main", "plugin_graphVizStructure_nodeBgColor", u"")
    if val != u"":
        nodeStyle.append(u'fillcolor="%s"' % val)
    
    nodeStyle = "node [" + u", ".join(nodeStyle) + u"]"
 
    edgeStyle = [u'style=solid']
    
    val = config.get("main", "plugin_graphVizStructure_edgeColor", u"")
    if val != u"":
        edgeStyle.append(u'color="%s"' % val)

    edgeStyle = "edge [" + u", ".join(edgeStyle) + u"]"
    
    return nodeStyle + u"; " + edgeStyle



def buildRelationGraphSource(wikiDocument, currWord, config):
    wikiData = wikiDocument.getWikiData()

    global_excludeRe = None
    global_includeRe = None

    global_exclude_properties = [re.escape(p[2].strip()) for p in wikiDocument.getPropertyTriples(
                None, u'global.graph.relation.exclude', None)]

    if len(global_exclude_properties) > 0:
        global_excludeRe = re.compile(
                ur"^" + joinRegexes(global_exclude_properties) + ur"(?:\.|$)",
                re.DOTALL | re.UNICODE | re.MULTILINE)

    else:
        global_include_properties = [re.escape(p[2].strip()) for p in wikiDocument.getPropertyTriples(
                    None, u'global.graph.relation.include', None)]
        
        if len(global_include_properties) > 0:
            global_includeRe = re.compile(
                    ur"^" + joinRegexes(global_include_properties)+ ur"(?:\.|$)",
                    re.DOTALL | re.UNICODE | re.MULTILINE)

    graph = []
#     graph = [u'', u'digraph {','node [style=filled]']
#     
#     graph += _buildNodeDefs(wikiDocument, currWord)

    # construct edges

    word_properties = (p for p in wikiDocument.getPropertyTriples(None, None, None))

    if global_includeRe is not None:
        word_relations = (p for p in word_properties if global_includeRe.match(p[1]))
    elif global_excludeRe is not None:
        word_relations = (p for p in word_properties if not global_excludeRe.match(p[1]))
    else:
        word_relations = word_properties

    wordSet = set()

    # Unalias wikiwords/remove non-wikiwords in property values
    for p in word_relations:
        word = wikiDocument.filterAliasesWikiWord(p[2])
        if word is None:
            continue

        graph.append(u'"%s" -> "%s" [label="%s"];' % (p[0], word, p[1]))
        wordSet.add(p[0])
        wordSet.add(word)

    graph.append('}')

    if not currWord in wordSet:
        currWord = None

    return '\n'.join([u'\ndigraph {', _buildGraphStyle(config)] +
            _buildNodeDefs(wikiDocument, currWord, wordSet) + graph)



def buildChildGraphSource(wikiDocument, currWord, config):
    wikiData = wikiDocument.getWikiData()

    graph = [u'', u'digraph {', _buildGraphStyle(config)]

    graph += _buildNodeDefs(wikiDocument, currWord)

    conns = set()

    allWords = wikiData.getAllDefinedWikiPageNames()

    for word in allWords:
        for child in wikiData.getChildRelationships(word, existingonly=True,
                selfreference=False):
            child = wikiDocument.getAliasesWikiWord(child)

            conns.add((word, child))

    for word, child in conns:
        graph.append(u'"%s" -> "%s";' % (word, child))

    graph.append(u'}')
    return u'\n'.join(graph)






def describeInsertionKeys(ver, app):
    """
    API function for "InsertionByKey" plugins
    Returns a sequence of tuples describing the supported
    insertion keys. Each tuple has the form (insKey, exportTypes, handlerFactory)
    where insKey is the insertion key handled, exportTypes is a sequence of
    strings describing the supported export types and handlerFactory is
    a factory function (normally a class) taking the wxApp object as
    parameter and returning a handler object fulfilling the protocol
    for "insertion by key" (see EqnHandler as example).

    ver -- API version (can only be 1 currently)
    app -- wxApp object
    """
    return (
            (u"graph.relation", ("html_single", "html_previewWX", "html_preview", "html_multi"), DotHandler),
            (u"graph.child", ("html_single", "html_previewWX", "html_preview", "html_multi"), DotHandler)
            )


class GraphVizBaseHandler:
    """
    Base class fulfilling the "insertion by key" protocol.
    """
    # Filled in by derived classes
    EXAPPNAME = ""
    EXECONFIGKEY = ""
    
    def __init__(self, app):
        self.app = app
        self.extAppExe = None
        
    def findExe(self):
        # Find MimeTeX executable by configuration setting
        dirPath = self.app.getGlobalConfig().get("main",
                "plugin_graphViz_dirExe", "")
        if not dirPath:
            self.extAppExe = ""
            return
            
        exeName = self.app.getGlobalConfig().get("main", self.EXECONFIGKEY, "")
        self.extAppExe = os.path.join(dirPath, exeName)
        
        
    def taskStart(self, exporter, exportType):
        """
        This is called before any call to createContent() during an
        export task.
        An export task can be a single HTML page for
        preview or a single page or a set of pages for export.
        exporter -- Exporter object calling the handler
        exportType -- string describing the export type
        
        Calls to createContent() will only happen after a 
        call to taskStart() and before the call to taskEnd()
        """
        self.findExe()

        
    def taskEnd(self):
        """
        Called after export task ended and after the last call to
        createContent().
        """
        pass


    def createContent(self, exporter, exportType, insToken):
        """
        Handle an insertion and create the appropriate content.

        exporter -- Exporter object calling the handler
        exportType -- string describing the export type
        insToken -- insertion token to create content for (see also 
                PageAst.Insertion)

        An insertion token has the following member variables:
            key: insertion key (unistring)
            value: value of an insertion (unistring)
            appendices: sequence of strings with the appendices

        Meaning and type of return value is solely defined by the type
        of the calling exporter.
        
        For HtmlXmlExporter a unistring is returned with the HTML code
        to insert instead of the insertion.        
        """
        
        if insToken.key == u"graph.relation":
            source = buildRelationGraphSource(exporter.getWikiDocument(),
                    insToken.value, exporter.getMainControl().getConfig())
        else:    # insToken.key == u"graph.child"
            source = buildChildGraphSource(exporter.getWikiDocument(),
                    insToken.value, exporter.getMainControl().getConfig())

        if not source:
            # Nothing in, nothing out
            return u""

        response, url = self.createImage(exporter.getTempFileSet(), exportType,
                source, insToken.appendices)

        if response is not None:
            return u"<pre>" + (u"[%s]" % response)+ \
                    "</pre>"

        # Return appropriate HTML code for the image
        if exportType == "html_previewWX":
            # Workaround for internal HTML renderer
            return (u'<img src="%s" border="0" align="bottom" alt="formula" />'
                    u'&nbsp;') % url
        else:
            return u'<img src="%s" border="0" align="bottom" alt="formula" />' \
                    % url



    def createImage(self, tempFileSet, exportType, source, insParams):
        """
        """
        # Retrieve quoted content of the insertion
        
        if self.extAppExe == "":
            # No path to executable -> show message
            return u"Please set path to GraphViz executables in options", None

        # Get exporters temporary file set (manages creation and deletion of
        # temporary files)
        tfs = tempFileSet
        source = lineendToOs(utf8Enc(source, "replace")[0])

        pythonUrl = (exportType != "html_previewWX")
        dstFullPath = tfs.createTempFile("", ".png", relativeTo="")
        url = tfs.getRelativeUrl(None, dstFullPath, pythonUrl=pythonUrl)

        # Store token content in a temporary file
        srcfilepath = createTempFile(source, ".dot")
        try:
            cmdline = list2cmdline((self.extAppExe, "-Tpng", "-o" + dstFullPath,
                    srcfilepath))

            # Run external application
            childIn, childOut, childErr = os.popen3(cmdline, "b")

            if u"noerror" in [a.strip() for a in insParams]:
                childErr.read()
                errResponse = None
            else:
                errResponse = childErr.read()
        finally:
            os.unlink(srcfilepath)

        if errResponse is not None and errResponse != "":
            appname = mbcsDec(self.EXAPPNAME, "replace")[0]
            errResponse = mbcsDec(errResponse, "replace")[0]
            return (_(u"%s Error: %s") % (appname, errResponse)), None

        return None, url



    def getExtraFeatures(self):
        """
        Returns a list of bytestrings describing additional features supported
        by the plugin. Currently not specified further.
        """
        return ()
        


class DotHandler(GraphVizBaseHandler):
    EXAPPNAME = "Dot"
    EXECONFIGKEY = "plugin_graphViz_exeDot"

class NeatoHandler(GraphVizBaseHandler):
    EXAPPNAME = "Neato"
    EXECONFIGKEY = "plugin_graphViz_exeNeato"

class TwopiHandler(GraphVizBaseHandler):
    EXAPPNAME = "Twopi"
    EXECONFIGKEY = "plugin_graphViz_exeTwopi"

class CircoHandler(GraphVizBaseHandler):
    EXAPPNAME = "Circo"
    EXECONFIGKEY = "plugin_graphViz_exeCirco"

class FdpHandler(GraphVizBaseHandler):
    EXAPPNAME = "Fdp"
    EXECONFIGKEY = "plugin_graphViz_exeFdp"



# -------- Menu function implementation starts here --------


def describeMenuItems(wiki):
    """
    wiki -- Calling PersonalWikiFrame
    Returns a sequence of tuples to describe the menu items, where each must
    contain (in this order):
        - callback function
        - menu item string
        - menu item description (string to show in status bar)
    It can contain the following additional items (in this order), each of
    them can be replaced by None:
        - icon descriptor (see below, if no icon found, it won't show one)
        - menu item id.

    The  callback function  must take 2 parameters:
        wiki - Calling PersonalWikiFrame
        evt - wx.CommandEvent

    An  icon descriptor  can be one of the following:
        - a wx.Bitmap object
        - the filename of a bitmap (if file not found, no icon is used)
        - a tuple of filenames, first existing file is used
    """
    
    kb = wiki.getKeyBindings()
    
    return (
            (showGraphViz, _(u"Show relation graph") + u"\t" +
            kb.Plugin_GraphVizStructure_ShowRelationGraph, _(u"Show relation graph")),
           
            (showGraphSource, _(u"Show rel. graph source") + u"\t" +
            kb.Plugin_GraphVizStructure_ShowRelationGraphSource,
            _(u"Show relation graph source")),

            (showChildGraph, _(u"Show child graph") + u"\t" +
            kb.Plugin_GraphVizStructure_ShowChildGraph, _(u"Show child graph")),

            (showChildGraphSource, _(u"Show child graph source") + u"\t" +
            kb.Plugin_GraphVizStructure_ShowChildGraphSource,
            _(u"Show child graph source"))
            )


class GraphView(wx.html.HtmlWindow):
    def __init__(self, presenter, parent, ID, mode="relation graph/dot"):
        wx.html.HtmlWindow.__init__(self, parent, ID)
        self.presenter = presenter
        self.graphDotHandler = DotHandler(wx.GetApp())
        self.graphDotHandler.findExe()

        self.visible = False
        self.outOfSync = True

        self.tempFileSet = TempFileSet()
        self._updateTempFilePrefPath()
        
        self.mode = mode
        
        wx.EVT_MENU(self, GUI_ID.CMD_CLIPBOARD_COPY, self.OnClipboardCopy)


    def _updateTempFilePrefPath(self):
#         wikiDoc = self.presenter.getWikiDocument()
# 
#         if wikiDoc is not None:
#             self.tempFileSet.setPreferredPath(wikiDoc.getWikiTempDir())
#         else:
        self.tempFileSet.setPreferredPath(None)


    def close(self):
        self.tempFileSet.clear()

#         self.Unbind(wx.EVT_SET_FOCUS)
#         self.setLayerVisible(False)
#         self.presenterListener.disconnect()
#         self.__sinkApp.disconnect()
#         self.__sinkDocPage.disconnect()


    def setLayerVisible(self, vis, scName=""):
        """
        Informs the widget if it is really visible on the screen or not
        """
        if not self.visible and vis:
            self.outOfSync = True   # Just to be sure
            self.refresh()
            
        if not vis:
            self.tempFileSet.clear()

        self.visible = vis


    def setMode(self, mode):
        if self.mode == mode:
            return

        self.mode = mode
        self.outOfSync = True   # Just to be sure
        self.refresh()


    def refresh(self):
        if self.outOfSync:
            self.graphDotHandler.findExe()
            wikiPage = self.presenter.getDocPage()
            if wikiPage is None:
                return  # TODO Do anything else here?
                
            word = wikiPage.getWikiWord()
            if word is None:
                return  # TODO Do anything else here?

            # Remove previously used temporary files
            self.tempFileSet.clear()

            if self.mode.startswith("relation graph/"):
                source = buildRelationGraphSource(
                        self.presenter.getWikiDocument(), word,
                        self.presenter.getMainControl().getConfig())
            else:  # self.mode.startswith("child graph/"):
                source = buildChildGraphSource(
                        self.presenter.getWikiDocument(), word,
                        self.presenter.getMainControl().getConfig())

            if self.mode.endswith("/dot"):
                response, url = self.graphDotHandler.createImage(self.tempFileSet,
                        "html_previewWX", source, [])

                if response:
                    self.presenter.displayErrorMessage(response)
                    self.outOfSync = False
                    return

                self.SetPage(uniToGui(u'<img src="%s" border="0" align="top" alt="relation" />'
                        % url))

            else:  # self.mode.endswith("/dot/source"):
                if self.graphDotHandler.extAppExe == "":
                    # No path to executable -> show message
                    warning = u"To see the graph, you must install GraphViz executable\n"\
                            u"and set the path to it in options\n\n"
                else:
                    warning = u""

                self.SetPage(uniToGui(u'<pre>%s%s</pre>' %
                        (escapeHtmlNoBreaks(warning), escapeHtmlNoBreaks(source))))

        self.outOfSync = False


    def OnClipboardCopy(self, evt):
        copyTextToClipboard(self.SelectionToText())






def showGraphViz(wiki, evt):
#     wikiWord = wiki.getCurrentWikiWord()
#     if wikiWord is None:
#         return
    
    presenter = wiki.getCurrentDocPagePresenter()
    rc = presenter.getSubControl("graph view")
    if rc is None:
        presenter.setSubControl("graph view", GraphView(presenter,
                presenter, -1, "relation graph/dot"))
    else:
        rc.setMode("relation graph/dot")
    
    presenter.switchSubControl("graph view")



def showGraphSource(wiki, evt):
#     wikiWord = wiki.getCurrentWikiWord()
#     if wikiWord is None:
#         return
    
    presenter = wiki.getCurrentDocPagePresenter()
    rc = presenter.getSubControl("graph view")
    if rc is None:
        presenter.setSubControl("graph view", GraphView(presenter,
                presenter, -1, "relation graph/dot/source"))
    else:
        rc.setMode("relation graph/dot/source")
    
    presenter.switchSubControl("graph view")



def showChildGraph(wiki, evt):
    wikiWord = wiki.getCurrentWikiWord()
    if wikiWord is None:
        return
    
    presenter = wiki.getCurrentDocPagePresenter()
    rc = presenter.getSubControl("graph view")
    if rc is None:
        presenter.setSubControl("graph view", GraphView(presenter,
                presenter, -1, "child graph/dot"))
    else:
        rc.setMode("child graph/dot")

    presenter.switchSubControl("graph view")



def showChildGraphSource(wiki, evt):
    wikiWord = wiki.getCurrentWikiWord()
    if wikiWord is None:
        return
    
    presenter = wiki.getCurrentDocPagePresenter()
    rc = presenter.getSubControl("graph view")
    if rc is None:
        presenter.setSubControl("graph view", GraphView(presenter,
                presenter, -1, "child graph/dot/source"))
    else:
        rc.setMode("child graph/dot/source")
    
    presenter.switchSubControl("graph view")



def registerOptions(ver, app):
    """
    API function for "Options" plugins
    Register configuration options and their GUI presentation
    ver -- API version (can only be 1 currently)
    app -- wxApp object
    """
    # Register options
    dgcd = app.getDefaultGlobalConfigDict()
    dgcd[("main", "plugin_graphVizStructure_nodeFacename")] = u""
    dgcd[("main", "plugin_graphVizStructure_nodeFontsize")] = u"0"
    dgcd[("main", "plugin_graphVizStructure_nodeBorderColor")] = u""
    dgcd[("main", "plugin_graphVizStructure_nodeBgColor")] = u""
    dgcd[("main", "plugin_graphVizStructure_edgeColor")] = u""

    # Register panel in options dialog
    app.addOptionsDlgPanel(GraphVizStructOptionsPanel, _(u"  GraphVizStructure"))



class GraphVizStructOptionsPanel(PluginOptionsPanel):
    def __init__(self, parent, optionsDlg, app):
        """
        Called when "Options" dialog is opened to show the panel.
        Transfer here all options from the configuration file into the
        text fields, check boxes, ...
        """
        PluginOptionsPanel.__init__(self, parent, optionsDlg, app)
        
        mainsizer = wx.FlexGridSizer(5, 3, 0, 0)
        mainsizer.AddGrowableCol(1, 1)
        
        self.tfFacename = wx.TextCtrl(self, -1)
        facenameButton = wx.Button(self, -1, _(u"..."))
        facenameButton.SetMinSize((20, -1))

        mainsizer.Add(wx.StaticText(self, -1, _(u"Node font name:")), 0,
                wx.ALL | wx.EXPAND, 5)
        mainsizer.Add(self.tfFacename, 1, wx.ALL | wx.EXPAND, 5)
        mainsizer.Add(facenameButton, 0, wx.ALL | wx.EXPAND | wx.ALIGN_BOTTOM, 5)

        self.addOptionEntry("plugin_graphVizStructure_nodeFacename",
                self.tfFacename, "t")
        
        wx.EVT_BUTTON(self, facenameButton.GetId(), self.OnSelectFaceNode)


        ctl = wx.TextCtrl(self, -1)
        mainsizer.Add(wx.StaticText(self, -1, _(u"Node font size:")), 0,
                wx.ALL | wx.EXPAND, 5)
        mainsizer.Add(ctl, 1, wx.ALL | wx.EXPAND, 5)
        mainsizer.Add((0, 0), 1)

        self.addOptionEntry("plugin_graphVizStructure_nodeFontsize", ctl, "i0+")


        ctl = wx.TextCtrl(self, -1)
        colorButton = wx.Button(self, -1, _(u"..."))
        colorButton.SetMinSize((20, -1))

        mainsizer.Add(wx.StaticText(self, -1, _(u"Node border color:")), 0,
                wx.ALL | wx.EXPAND, 5)
        mainsizer.Add(ctl, 1, wx.ALL | wx.EXPAND, 5)
        mainsizer.Add(colorButton, 0, wx.ALL | wx.EXPAND | wx.ALIGN_BOTTOM, 5)

        self.addOptionEntry("plugin_graphVizStructure_nodeBorderColor", ctl,
                "color0", colorButton)


        ctl = wx.TextCtrl(self, -1)
        colorButton = wx.Button(self, -1, _(u"..."))
        colorButton.SetMinSize((20, -1))

        mainsizer.Add(wx.StaticText(self, -1, _(u"Node background color:")), 0,
                wx.ALL | wx.EXPAND, 5)
        mainsizer.Add(ctl, 1, wx.ALL | wx.EXPAND, 5)
        mainsizer.Add(colorButton, 0, wx.ALL | wx.EXPAND | wx.ALIGN_BOTTOM, 5)

        self.addOptionEntry("plugin_graphVizStructure_nodeBgColor", ctl,
                "color0", colorButton)


        ctl = wx.TextCtrl(self, -1)
        colorButton = wx.Button(self, -1, _(u"..."))
        colorButton.SetMinSize((20, -1))

        mainsizer.Add(wx.StaticText(self, -1, _(u"Edge color:")), 0,
                wx.ALL | wx.EXPAND, 5)
        mainsizer.Add(ctl, 1, wx.ALL | wx.EXPAND, 5)
        mainsizer.Add(colorButton, 0, wx.ALL | wx.EXPAND | wx.ALIGN_BOTTOM, 5)

        self.addOptionEntry("plugin_graphVizStructure_edgeColor", ctl,
                "color0", colorButton)

        self.SetSizer(mainsizer)
        self.Fit()
        
        self.mainControl = optionsDlg.getMainControl()
        self.transferOptionsToDialog(self.mainControl.getConfig())


    def setVisible(self, vis):
        """
        Called when panel is shown or hidden. The actual wxWindow.Show()
        function is called automatically.
        
        If a panel is visible and becomes invisible because another panel is
        selected, the plugin can veto by returning False.
        When becoming visible, the return value is ignored.
        """
        return True

    def handleOk(self):
        """
        This is called if checkOk() returned True for all panels. Transfer here
        all values from text fields, checkboxes, ... into the configuration
        file.
        """
        self.transferDialogToOptions(self.mainControl.getConfig())


    def OnSelectFaceNode(self, evt):
        dlg = FontFaceDialog(self, -1, self.mainControl,
                self.tfFacename.GetValue())
        if dlg.ShowModal() == wx.ID_OK:
            self.tfFacename.SetValue(dlg.GetValue())
        dlg.Destroy()