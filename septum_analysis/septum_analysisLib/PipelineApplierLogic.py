import qt
from .CalculatorVolume import *


class PipelineApplierLogic:
    def __init__(self, updaterActions, creatorDataStorage):
        self.actions = []
        self.updaterActions = updaterActions
        self.creatorDataStorage = creatorDataStorage

    def addAction(self, action):
        self.actions.append(action)

    def run(self, calculatorVolume: CalculatorVolume, ijkPoints):
        data = self.creatorDataStorage(calculatorVolume, ijkPoints)

        self.updaterActions.start()
        for index, action in enumerate(self.actions):
            action(data)
            self.updaterActions.update(index, len(self.actions))
        self.updaterActions.finish()


class EditorEffectAction:
    def __init__(self, effectName, getterParameters: dict, otherApplyAction = None):
        self.effectName = effectName
        self.getterParameters = getterParameters
        self.applyAction = otherApplyAction
        if self.applyAction is None:
            self.applyAction = lambda data, effect: effect.self().onApply()

    def __call__(self, data, *args, **kwargs):
        data.segmentEditorWidget.setActiveEffectByName(self.effectName)
        effect = data.segmentEditorWidget.activeEffect()
        for nameParameter, getter in self.getterParameters.items():
            effect.setParameter(nameParameter, getter(data))
        self.applyAction(data, effect)
        data.segmentEditorWidget.setActiveEffectByName(None)

class UpdaterActionsOnProgressBar:
    def __init__(self, uiContainer):
        self.progressBar: qt.QProgressBar = uiContainer.progressBarForCalculatorVolume

    def start(self):
        self.progressBar.setValue(0)
        self.progressBar.show()

    def update(self, i, size):
        self.progressBar.setValue(float(i) / float(size) * 100)
        pass

    def finish(self):
        self.progressBar.setValue(100)
        self.progressBar.hide()

