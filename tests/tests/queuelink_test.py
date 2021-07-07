# -*- coding: utf-8 -*-
from __future__ import unicode_literals
import time
import unittest

from multiprocessing import Manager

try:  # Python 2.7
    from Queue import Empty
except ImportError:  # Python 3.x
    from queue import Empty

from tests.tests import context
from processrunner.queuelink import QueueLink


'''
'''
class ProcessRunnerQueueLinkTestCase(unittest.TestCase):
    def setUp(self):
        self.manager = Manager()

    def test_processrunner_queuelink_get_client_id(self):
        queue_proxy = self.manager.JoinableQueue()
        queue_link = QueueLink(name="test_link")
        client_id = queue_link.registerQueue(queue_proxy=queue_proxy,
                                             direction="source")

        self.assertIsNotNone(client_id,
                             "registerQueue did not return a client ID.")

        # Should be able to cast this to an int
        client_id_int = int(client_id)

        self.assertIsInstance(client_id_int,
                              int,
                              "registerQueue did not return an int client ID.")

    def test_processrunner_queuelink_source_destination_movement(self):
        text_in = "a😂" * 10
        source_q = self.manager.JoinableQueue()
        dest_q = self.manager.JoinableQueue()
        queue_link = QueueLink(name="test_link")

        source_id = queue_link.registerQueue(queue_proxy=source_q,
                                             direction="source")
        dest_id = queue_link.registerQueue(queue_proxy=dest_q,
                                           direction="destination")

        source_q.put(text_in)
        text_out = dest_q.get()

        self.assertEqual(text_in,
                         text_out,
                         "Text isn't the same across the link")


if __name__ == "__main__":
    suite = unittest.TestLoader().loadTestsFromTestCase(ProcessRunnerQueueLinkTestCase)
    unittest.TextTestRunner(verbosity=2).run(suite)
