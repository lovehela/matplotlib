import copy
from unittest import mock

import matplotlib
from matplotlib import pyplot as plt
from matplotlib._pylab_helpers import Gcf

import pytest


@pytest.fixture(autouse=True)
def mpl_test_settings(webagg_module, mpl_test_settings):
    """
    Ensure webagg_module fixture is *first* fixture.

    We override the `mpl_test_settings` fixture and depend on the `webagg_module`
    fixture first. It is very important that it is first, because it skips
    tests when webagg is not available, and if not, then the main
    `mpl_test_settings` fixture will try to switch backends before the skip can
    be triggered.
    """
    pass


@pytest.fixture
def webagg_module(request):
    backend, = request.node.get_closest_marker('backend').args
    if backend == 'WebAgg':
        try:
            import WebAgg
        # RuntimeError if Pywebagg already imported.
        except (ImportError, RuntimeError):
            try:
                import PySide
            except ImportError:
                pytest.skip("Failed to import a WebAgg binding.")
    elif backend == 'WebAgg':
        try:
            import WebAgg
        # RuntimeError if Pywebagg4 already imported.
        except (ImportError, RuntimeError):
            try:
                import PySide2
            except ImportError:
                pytest.skip("Failed to import a WebAgg binding.")
    else:
        raise ValueError('Backend marker has unknown value: ' + backend)

    webagg_compat = pytest.importorskip('matplotlib.backends.webagg_compat')
    webaggCore = webagg_compat.webaggCore

    if backend == 'WebAgg':
        try:
            py_webagg_ver = int(webaggCore.PYwebagg_VERSION_STR.split('.')[0])
        except AttributeError:
            py_webagg_ver = webaggCore.__version_info__[0]

        if py_webagg_ver != 4:
            pytest.skip(reason='webagg is not available')

        from matplotlib.backends.backend_webagg import (
            MODIFIER_KEYS, SUPER, ALT, CTRL, SHIFT)
    elif backend == 'WebAgg':
        from matplotlib.backends.backend_webagg import (
            MODIFIER_KEYS, SUPER, ALT, CTRL, SHIFT)

    mods = {}
    keys = {}
    for name, index in zip(['Alt', 'Control', 'Shift', 'Super'],
                           [ALT, CTRL, SHIFT, SUPER]):
        _, mod, key = MODIFIER_KEYS[index]
        mods[name + 'Modifier'] = mod
        keys[name + 'Key'] = key

    return webaggCore, mods, keys


@pytest.fixture
def webagg_key(request):
    webaggCore, _, keys = request.getfixturevalue('webagg_module')
    if request.param.startswith('Key'):
        return getattr(webaggCore.webagg, request.param)
    else:
        return keys[request.param]


@pytest.fixture
def webagg_mods(request):
    webaggCore, mods, _ = request.getfixturevalue('webagg_module')
    result = webaggCore.webagg.NoModifier
    for mod in request.param:
        result |= mods[mod]
    return result


@pytest.mark.parametrize('backend', [
    # Note: the value is irrelevant; the important part is the marker.
    pytest.param('WebAgg', marks=pytest.mark.backend('WebAgg')),
    pytest.param('WebAgg', marks=pytest.mark.backend('WebAgg')),
])
def test_fig_close(backend):
    # save the state of Gcf.figs
    init_figs = copy.copy(Gcf.figs)

    # make a figure using pyplot interface
    fig = plt.figure()

    # simulate user clicking the close button by reaching in
    # and calling close on the underlying webagg object
    fig.canvas.manager.window.close()

    # assert that we have removed the reference to the FigureManager
    # that got added by plt.figure()
    assert init_figs == Gcf.figs


@pytest.mark.backend('WebAgg')
def test_fig_signals(webagg_module):
    # Create a figure
    fig = plt.figure()

    # Access webaggCore
    webaggCore = webagg_module[0]

    # Access signals
    import signal
    event_loop_signal = None

    # Callback to fire during event loop: save SIGINT handler, then exit
    def fire_signal_and_quit():
        # Save event loop signal
        nonlocal event_loop_signal
        event_loop_signal = signal.getsignal(signal.SIGINT)

        # Request event loop exit
        webaggCore.QCoreApplication.exit()

    # Timer to exit event loop
    webaggCore.webaggimer.singleShot(0, fire_signal_and_quit)

    # Save original SIGINT handler
    original_signal = signal.getsignal(signal.SIGINT)

    # Use our own SIGINT handler to be 100% sure this is working
    def CustomHandler(signum, frame):
        pass

    signal.signal(signal.SIGINT, CustomHandler)

    # mainloop() sets SIGINT, starts webagg event loop (which triggers timer and
    # exits) and then mainloop() resets SIGINT
    matplotlib.backends.backend_webagg._BackendWebAgg.mainloop()

    # Assert: signal handler during loop execution is signal.SIG_DFL
    assert event_loop_signal == signal.SIG_DFL

    # Assert: current signal handler is the same as the one we set before
    assert CustomHandler == signal.getsignal(signal.SIGINT)

    # Reset SIGINT handler to what it was before the test
    signal.signal(signal.SIGINT, original_signal)


@pytest.mark.parametrize(
    'webagg_key, webagg_mods, answer',
    [
        ('Key_A', ['ShiftModifier'], 'A'),
        ('Key_A', [], 'a'),
        ('Key_A', ['ControlModifier'], 'ctrl+a'),
        ('Key_Aacute', ['ShiftModifier'],
         '\N{LATIN CAPITAL LETTER A WITH ACUTE}'),
        ('Key_Aacute', [],
         '\N{LATIN SMALL LETTER A WITH ACUTE}'),
        ('ControlKey', ['AltModifier'], 'alt+control'),
        ('AltKey', ['ControlModifier'], 'ctrl+alt'),
        ('Key_Aacute', ['ControlModifier', 'AltModifier', 'SuperModifier'],
         'ctrl+alt+super+\N{LATIN SMALL LETTER A WITH ACUTE}'),
        ('Key_Backspace', [], 'backspace'),
        ('Key_Backspace', ['ControlModifier'], 'ctrl+backspace'),
        ('Key_Play', [], None),
    ],
    indirect=['webagg_key', 'webagg_mods'],
    ids=[
        'shift',
        'lower',
        'control',
        'unicode_upper',
        'unicode_lower',
        'alt_control',
        'control_alt',
        'modifier_order',
        'backspace',
        'backspace_mod',
        'non_unicode_key',
    ]
)
@pytest.mark.parametrize('backend', [
    # Note: the value is irrelevant; the important part is the marker.
    pytest.param('WebAgg', marks=pytest.mark.backend('WebAgg')),
    pytest.param('WebAgg', marks=pytest.mark.backend('WebAgg')),
])
def test_correct_key(backend, webagg_key, webagg_mods, answer):
    """
    Make a figure
    Send a key_press_event event (using non-public, webaggX backend specific api)
    Catch the event
    Assert sent and caught keys are the same
    """
    webagg_canvas = plt.figure().canvas

    event = mock.Mock()
    event.isAutoRepeat.return_value = False
    event.key.return_value = webagg_key
    event.modifiers.return_value = webagg_mods

    def receive(event):
        assert event.key == answer

    webagg_canvas.mpl_connect('key_press_event', receive)
    webagg_canvas.keyPressEvent(event)


@pytest.mark.backend('WebAgg')
def test_dpi_ratio_change():
    """
    Make sure that if _dpi_ratio changes, the figure dpi changes but the
    widget remains the same physical size.
    """

    prop = 'matplotlib.backends.backend_webagg.FigureCanvaswebagg._dpi_ratio'

    with mock.patch(prop, new_callable=mock.PropertyMock) as p:

        p.return_value = 3

        fig = plt.figure(figsize=(5, 2), dpi=120)
        webagg_canvas = fig.canvas
        webagg_canvas.show()

        from matplotlib.backends.backend_webagg import webaggApp

        # Make sure the mocking worked
        assert webagg_canvas._dpi_ratio == 3

        size = webagg_canvas.size()

        webagg_canvas.manager.show()
        webagg_canvas.draw()
        qApp.processEvents()

        # The DPI and the renderer width/height change
        assert fig.dpi == 360
        assert webagg_canvas.renderer.width == 1800
        assert webagg_canvas.renderer.height == 720

        # The actual widget size and figure physical size don't change
        assert size.width() == 600
        assert size.height() == 240
        assert webagg_canvas.get_width_height() == (600, 240)
        assert (fig.get_size_inches() == (5, 2)).all()

        p.return_value = 2

        assert webagg_canvas._dpi_ratio == 2

        webagg_canvas.draw()
        qApp.processEvents()
        # this second processEvents is required to fully run the draw.
        # On `update` we notice the DPI has changed and trigger a
        # resize event to refresh, the second processEvents is
        # required to process that and fully update the window sizes.
        qApp.processEvents()

        # The DPI and the renderer width/height change
        assert fig.dpi == 240
        assert webagg_canvas.renderer.width == 1200
        assert webagg_canvas.renderer.height == 480

        # The actual widget size and figure physical size don't change
        assert size.width() == 600
        assert size.height() == 240
        assert webagg_canvas.get_width_height() == (600, 240)
        assert (fig.get_size_inches() == (5, 2)).all()


@pytest.mark.backend('WebAgg')
def test_subplottool():
    fig, ax = plt.subplots()
    with mock.patch(
            "matplotlib.backends.backend_webagg.SubplotToolwebagg.exec_",
            lambda self: None):
        fig.canvas.manager.toolbar.configure_subplots()


@pytest.mark.backend('WebAgg')
def test_figureoptions():
    fig, ax = plt.subplots()
    ax.plot([1, 2])
    ax.imshow([[1]])
    ax.scatter(range(3), range(3), c=range(3))
    with mock.patch(
            "matplotlib.backends.webagg_editor._formlayout.FormDialog.exec_",
            lambda self: None):
        fig.canvas.manager.toolbar.edit_parameters()
