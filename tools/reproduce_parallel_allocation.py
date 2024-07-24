#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.
from collections import Counter
import threading
import uuid

import click
import pyccloud


class Bla(threading.Thread):

    def __init__(self, *args, p, uuid_, signal, results, generation=None,
                 **kwargs):
        self._p = p
        self._uuid = uuid_
        self._signal = signal
        self._results = results
        self._generation = generation
        super().__init__(*args, **kwargs)

    def run(self):
        requested_memory_mb = 120 * 1024

        data = {
            'allocations': {
                'd29b6d53-af4a-4fd0-8f5a-149b600f9b59': {
                    'resources': {
                        'MEMORY_MB': requested_memory_mb,
                    },
                },
            },
            'consumer_generation': self._generation,
            'user_id': '02613c7c5763fba364fc5cacdf5aca1d38fc'
                       'f70bad0d8a52fe6e51d85c8147d1',
            'project_id': '7db511c1805f4a7ba57abc822c7b8835',
            'consumer_type': 'INSTANCE',
        }

        self._signal.wait()

        resp = self._p.put(f"/allocations/{self._uuid}", json=data)
        self._results.append((self._uuid, resp.status_code))
        print(f"{resp.status_code}: {resp.text}")


@click.command()
def main():
    N = 8
    # which region do I fill up? qa-de-3 probably
    ca = pyccloud.CloudAnalyzer.from_autoconf()

    p = ca.os_admin.api.placement
    p.default_microversion = 1.38

    uuids = [str(uuid.uuid4()) for _ in range(N)]
    print(uuids)

    signal = threading.Barrier(N)
    threads = []
    results = []

    for uuid_ in uuids:
        # how to parallel? threads? processes? shell?
        # let's try threads, all waiting for the same signal after start
        t = Bla(p=p, uuid_=uuid_, signal=signal, results=results)
        threads.append(t)
        t.start()

    for t in threads:
        t.join()

    generations = {uuid_: 1 if status == 204 else None
                   for uuid_, status in results}
    print(Counter(r[1] for r in results))

    for uuid_ in uuids:
        print(uuid_)
        print(p.get(f"/allocations/{uuid_}").json())

    signal = threading.Barrier(N)
    threads = []
    results = []

    for uuid_ in uuids:
        # how to parallel? threads? processes? shell?
        # let's try threads, all waiting for the same signal after start
        t = Bla(p=p, uuid_=uuid_, signal=signal, results=results,
                generation=generations[uuid_])
        threads.append(t)
        t.start()

    for t in threads:
        t.join()

    print(Counter(r[1] for r in results))

    for uuid_ in uuids:
        print(uuid_)
        print(p.get(f"/allocations/{uuid_}").json())

    if click.confirm('Delete them?'):
        for uuid_ in uuids:
            p.delete(f"/allocations/{uuid_}")


if __name__ == '__main__':
    main()
