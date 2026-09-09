"""Keep the application to one instance.

Clicking the panel item runs `claude-statusbar --gui` afresh every time, so
without this you collect a new window per click.  A second launch hands its
request to the instance already running and exits.
"""

import os

from PySide6.QtNetwork import QLocalServer, QLocalSocket

from claude_statusbar.paths import APP_ID


def socket_name():
    """Per-user, so two logins on one machine don't collide."""
    try:
        return f"{APP_ID}-{os.getuid()}"
    except AttributeError:          # Windows has no getuid
        return f"{APP_ID}-{os.environ.get('USERNAME', 'user')}"


class SingleInstance:
    """Owns the socket if this is the first instance."""

    def __init__(self):
        self.server = None

    def hand_over(self, message=b"show"):
        """True if another instance took the request; this one should exit."""
        socket = QLocalSocket()
        socket.connectToServer(socket_name())
        if socket.waitForConnected(400):
            socket.write(message)
            socket.flush()
            socket.waitForBytesWritten(400)
            socket.disconnectFromServer()
            return True
        return False

    def listen(self, on_message):
        """Claim the socket and call on_message when another launch arrives."""
        # A crash leaves the socket file behind; nothing is listening on it,
        # so removing it here is safe and stops a permanent lockout.
        QLocalServer.removeServer(socket_name())
        self.server = QLocalServer()
        if not self.server.listen(socket_name()):
            self.server = None
            return False

        def accept():
            connection = self.server.nextPendingConnection()
            if connection is None:
                return
            connection.readyRead.connect(lambda: on_message())
            connection.disconnected.connect(connection.deleteLater)

        self.server.newConnection.connect(accept)
        return True
