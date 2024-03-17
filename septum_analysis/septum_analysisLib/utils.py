def registerEditorEffect(pathToDirectory: str, fileName: str) -> None:
    import os
    import qt
    import slicer.ScriptedLoadableModule

    import qSlicerSegmentationsEditorEffectsPythonQt as qSlicerSegmentationsEditorEffects
    instance = qSlicerSegmentationsEditorEffects.qSlicerSegmentEditorScriptedEffect(None)
    effectFilename = os.path.join(os.path.dirname(pathToDirectory), fileName)
    instance.setPythonSource(effectFilename.replace('\\', '/'))
    instance.self().register()
