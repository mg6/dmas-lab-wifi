import random
import re
import sys

NEIGHBOUR_DELAY = 1     # neighbour lookup delay
DISTANT_DELAY = 2       # route lookup delay
Q = 0.05                # link quality (drop ratio)


class Router:

    def __init__(self, i):
        self.id = i
        self.connections = {}       # neighbour -> delay
        self.input = []
        self.output = []
        self.routes = {}    # destination -> neighbour

    def add_connection(self, neighbour, delay, routes=[]):
        self.connections[neighbour] = delay

        for destination in routes:
            self.routes[destination] = neighbour

    def add_incoming_packet(self, packet):
        self.input.append(packet)

    def add_outgoing_packet(self, packet):
        self.output.append(packet)

    def get_route_for(self, destination):
        if destination in self.routes:
            return self.routes[destination]
        elif destination in self.connections:
            return destination
        else:
            return None

    def process_incoming_packets(self, i):
        for _ in range(len(self.input)):
            packet = self.input.pop(0)
            if packet.destination == self:      # to ourselves
                print('    delivered {}{} to {}'.format('REPLY ' if packet.is_reply else '', packet, self), file=sys.stderr)
                if packet.is_reply:
                    print('i={} conn={} node={} src={} dest={} status={}'.format(i, packet.connection, self.id, packet.source.id, packet.destination.id, 'delivered'))
                else:         # not a reply, respond to source router
                    via = self.get_route_for(packet.source)
                    lookup_delay = NEIGHBOUR_DELAY if via in self.connections else DISTANT_DELAY
                    reply_packet = Packet(
                        source=self,
                        destination=packet.source,
                        connection=packet.connection,
                        via=via,
                        delay=self.connections[via] + lookup_delay,
                        lifetime=packet.lifetime,
                        is_reply=True)
                    self.output.append(reply_packet)
            else:
                if packet.destination in self.connections:      # to our neighbour
                    packet.via = packet.destination
                    packet.delay = self.connections[packet.destination] + NEIGHBOUR_DELAY
                    self.output.append(packet)
                else:                               # to distant router
                    if packet.destination in self.routes:       # to distant router
                        via = self.routes[packet.destination]
                        packet.via = via
                        packet.delay = self.connections[via] + DISTANT_DELAY
                        self.output.append(packet)
                    else:
                        print('{} lost at {}'.format(packet, self), file=sys.stderr)

    def __str__(self):
        return "Router(id={} in=[{}] out=[{}])".format(
            self.id,
            ' '.join(map(str, self.input)),
            ' '.join(map(str, self.output)))


class Packet:

    def __init__(self, source, destination, connection=None, via=None, is_reply=False, delay=0, lifetime=0):
        self.source = source
        self.destination = destination
        self.connection = connection
        self.delay = delay
        self.via = via          # next hop to destination
        self.is_reply = is_reply
        self.lifetime = lifetime

    def set_delay(self, delay):
        self.delay = delay

    def tick(self):
        if self.delay is not None:
            self.delay -= 1

        self.lifetime += 1

        return self.delay

    def __str__(self):
        return "Packet(conn={} src={} dest={} via={} D={} T={})".format(
            self.connection,
            self.source.id,
            self.destination.id,
            self.via.id if self.via else None,
            self.delay,
            self.lifetime)


class Network:

    def __init__(self, routers, packets):
        self.routers = routers
        self.packets = packets

        for _ in range(len(self.packets)):
            packet = self.packets.pop(0)
            packet.source.add_incoming_packet(packet)

    def drop_packets(self, i):
        dropped = [packet for packet in self.packets if random.random() <= Q]
        for packet in dropped:
            print('dropped {}'.format(packet), file=sys.stderr)
            print('i={} conn={} node={} src={} dest={} status={}'.format(i, packet.connection, packet.via.id, packet.source.id, packet.destination.id, 'lost'))
        self.packets = [packet for packet in self.packets if packet not in dropped]

    def deliver_packets(self, i):
        for _ in range(len(self.packets)):
            packet = self.packets.pop(0)
            t = packet.tick()
            if type(t) is int:
                if t <= 0:
                    packet.via.add_incoming_packet(packet)
                    packet.via = None
                else:
                    self.packets.append(packet)

    def process_incoming_packets(self, i):
        for router in self.routers:
            router.process_incoming_packets(i)   # move to output queue

    def transmit_packets(self, i):
        for router in self.routers:
            for _ in range(len(router.output)):
                packet = router.output.pop(0)
                self.packets.append(packet)

    def tick(self, i):
        print("t = {}".format(i), file=sys.stderr)
        print("    pre-deliver: transmit: [{}]".format(' '.join(map(str, self.packets))), file=sys.stderr)
        self.drop_packets(i)
        self.deliver_packets(i)
        print("    post-deliver: routers: {}".format(' '.join(map(str, self.routers))), file=sys.stderr)
        self.process_incoming_packets(i)
        print("    pre-transmit: routers: {}".format(' '.join(map(str, self.routers))), file=sys.stderr)
        self.transmit_packets(i)
        print("    post-transmit: transmit: [{}]".format(' '.join(map(str, self.packets))), file=sys.stderr)

    def run(self):
        i = 0
        while True:
            i += 1
            self.tick(i)
            if self.finished():
                break

    def finished(self):
        return len(self.packets) == 0 and all(
            len(router.input) == 0 and len(router.output) == 0 for router in self.routers)

    def dump(self, i, phase="?"):
        print("""\
            t = {} phase = {}
                Routers: {!s}
                Transit: {!s}
        """.format(
            i, phase,
            ' '.join(map(str, self.routers)),
            ' '.join(map(str, self.packets))), file=sys.stderr)


def read_routers(file_name):
    routers = {}

    with open(file_name, 'r') as f:
        lines = f.readlines()
        total = lines.pop(0)

        # read routers
        for line in lines:
            node = re.match(r"[0-9]+", line).group(0)
            node = int(node)

            if not routers.get(node, None):
                routers[node] = Router(i=node)

        # read connections & routes
        for line in lines:
            node = re.match(r"[0-9]+", line).group(0)
            node = int(node)

            for neighbour, delay, routes in re.findall(r"([0-9]+) ([0-9]+) \[([0-9 ]*)\]", line):
                neighbour = int(neighbour)
                delay = int(delay)

                router = routers[node]
                other = routers[neighbour]

                routes = re.findall(r"[0-9]+", routes)
                routes = [routers[int(route)] for route in routes]

                router.add_connection(other, delay, routes=routes)
                other.add_connection(router, delay)

        return routers


def read_packets(file_name, routers):
    packets = []

    with open(file_name, 'r') as f:
        for line in f.readlines():
            connection, source, destination = line.strip().split(' ')
            source = routers[int(source)]
            destination = routers[int(destination)]
            packets.append(Packet(source, destination, connection=connection))

        return packets


def main():
    # r1 = Router(1)
    # r2 = Router(2)
    # r3 = Router(3)
    #
    # r1.add_connection(r2, 11, routes=[r3])
    # r2.add_connection(r1, 11)
    #
    # r3.add_connection(r2, 5, routes=[r1])
    # r2.add_connection(r3, 5)
    #
    # routers = [
    #     r1,
    #     r2,
    #     r3
    # ]
    #
    # packets = [
    #     Packet(r1, r3),
    #     Packet(r3, r2)
    # ]
    #

    routers = read_routers('topology.txt')
    packets = read_packets('scenario.txt', routers)

    net = Network(routers.values(), packets)
    net.run()


if __name__ == '__main__':
    main()