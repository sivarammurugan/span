import sys

class ProgressBar(object):
    """
    """
    def __init__(self, start=0, end=10, width=12, fill='#', blank='.',
                 fmt='[{fill}{blank}] {progress}%', incremental=True):
        """
        """
        super(ProgressBar, self).__init__()
        self.start = start
        self.end = end
        self.width = width
        self.fill = fill
        self.blank = blank
        self.format = fmt
        self.incremental = incremental
        self.step = 100.0 / width
        self.reset()

    def __iadd__(self, increment):
        """Increment the amount of progress in place.
        """
        increment = self._get_progress(increment)
        if self.progress + increment < 100.0:
            self.progress += increment
        else:
            self.progress = 100.0
        return self

    def __str__(self):
        """Represent the progress bar as a string.

        Returns
        -------
        formatted : str
            The progress bar formatted as a string
        """
        progressed = self.progress // self.step
        fill = progressed * self.fill
        blank = (self.width - progressed) * self.blank
        return self.format.format(fill=fill, blank=blank,
                                  progress=int(self.progress))

    __repr__ = __str__

    def _get_progress(self, increment):
        """Get the current amount of progress.

        Parameters
        ----------
        increment : int

        Returns
        -------
        prog : float
            The current amount of progress.
        """
        return increment * 100.0 / self.end

    def reset(self):
        """Reset the current amount of progress.

        Returns
        -------
        self : ProgressBar
            The current instance
        """
        self.progress = self._get_progress(self.start)
        return self


class AnimatedProgressBar(ProgressBar):
    """An animated progress bar.

    This class is useful for showing the progress of a process in a terminal.
    """
    def __init__(self, *args, **kwargs):
        """Constructor.
        """
        super(AnimatedProgressBar, self).__init__(*args, **kwargs)
        self.stdout = kwargs.get('stdout', sys.stdout)

    def show_progress(self):
        """Show the current progress, compensating for terminal existence.
        """
        c = '\r'
        try:
            is_terminal = self.stdout.isatty()
        except AttributeError:
            pass
        else:
            if is_terminal:
                c = '\n'

        self.stdout.write(c)
        self.stdout.write(str(self))
        self.stdout.flush()
