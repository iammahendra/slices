#!/usr/bin/python
################################################################################
# The Frenetic Project                                                         #
# frenetic@frenetic-lang.org                                                   #
################################################################################
# Licensed to the Frenetic Project by one or more contributors. See the        #
# NOTICE file distributed with this work for additional information            #
# regarding copyright and ownership. The Frenetic Project licenses this        #
# file to you under the following license.                                     #
#                                                                              #
# Redistribution and use in source and binary forms, with or without           #
# modification, are permitted provided the following conditions are met:       #
# - Redistributions of source code must retain the above copyright             #
#   notice, this list of conditions and the following disclaimer.              #
# - Redistributions in binary form must reproduce the above copyright          #
#   notice, this list of conditions and the following disclaimer in            #
#   the documentation or other materials provided with the distribution.       #
# - The names of the copyright holds and contributors may not be used to       #
#   endorse or promote products derived from this work without specific        #
#   prior written permission.                                                  #
#                                                                              #
# Unless required by applicable law or agreed to in writing, software          #
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT    #
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the     #
# LICENSE file distributed with this work for specific language governing      #
# permissions and limitations under the License.                               #
################################################################################
# /slices/netcore_test.py                                                      #
# Tests for netcore, datastructures for predicates and policies                #
################################################################################
import copy
import netcore as nc
from netcore import then
import unittest

blank_packet = nc.Packet({})
fields = {'srcmac': 1, 'dstmac': 2, 'ethtype': 3,
          'srcip': 4, 'dstip': 5, 'vlan': 6, 'protocol': 7,
          'srcport': 8, 'dstport': 9}
fields_neg = {'srcmac': -1, 'dstmac': -2, 'ethtype': -3,
          'srcip': -4, 'dstip': -5, 'vlan': -6, 'protocol': -7,
          'srcport': -8, 'dstport': -9}
full_packet = nc.Packet(fields)
nega_packet = nc.Packet(fields_neg)
exact_header = nc.nary_intersection([nc.Header(f, v)
                                     for f, v in fields.items()])

class TestPredicate(unittest.TestCase):
#   Basic tests for primitives make sure that the remaining tests are sane
    def test_boolean_predicates(self):
        self.assertTrue(nc.Top().match(blank_packet, (1, 1)))
        self.assertFalse(nc.Bottom().match(blank_packet, (1, 1)))

    def test_header_loc(self):
        switch = 3
        port = 7
        header = nc.inport(switch, port)
        self.assertTrue(header.match(blank_packet, (switch, port)))
        self.assertFalse(header.match(blank_packet, (switch+1, port)))
        self.assertFalse(header.match(blank_packet, (switch, port+1)))
        self.assertFalse(header.match(blank_packet, (switch+1, port+1)))

        switch_only = nc.inport(switch, 0)
        self.assertTrue(switch_only.match(blank_packet, (switch, 3234)))
        self.assertFalse(switch_only.match(blank_packet, (switch+1, 3234)))

        port_only = nc.inport(0, port)
        self.assertTrue(port_only.match(blank_packet, (2345, port)))
        self.assertFalse(port_only.match(blank_packet, (2345, port+1)))

    def test_header_other_match(self):
        for (field, value) in fields.items():
            self.assertTrue(nc.Header(field, value).match(full_packet, (1, 2)))

    def test_header_other_match_wild(self):
        for (field, value) in fields.items():
            self.assertTrue(nc.Header(field, 0).match(full_packet, (1, 2)))

    def test_header_other_mismatch(self):
        for (field, value) in fields.items():
            self.assertFalse(
                nc.Header(field, value+1).match(full_packet, (1, 2)))

    def test_header_phys(self):
        port_map = {(1,2):(5,10)}
        switch_map = {1:5}
        loc = nc.inport(1, 2)
        phys = loc.get_physical_predicate(port_map, switch_map)
        self.assertEquals((5, 10), phys.pattern)

        loc = nc.inport(1, 0)
        phys = loc.get_physical_predicate(port_map, switch_map)
        self.assertEquals((5, 0), phys.pattern)

        loc = nc.inport(0, 2)
        self.assertRaises(nc.PhysicalException,
            loc.get_physical_predicate, port_map, switch_map)

        fields = nc.Header('srcmac', 3)
        phys = fields.get_physical_predicate(port_map, switch_map)
        self.assertEquals(fields, phys)

    def test_union_match(self):
        loc = nc.inport(1,1)
        field = nc.Header('srcmac', 1)
        union = loc + field

        self.assertTrue(union.match(blank_packet, (1, 1)))

        self.assertTrue(union.match(fields_neg, (1, 1)))
        self.assertTrue(union.match(fields, (-1, -1)))
        self.assertTrue(union.match(fields, (1, 1)))
        self.assertFalse(union.match(fields_neg, (-1, -1)))

    def test_intersection_match(self):
        loc = nc.inport(1,1)
        field = nc.Header('srcmac', 1)
        inter = loc & field

        self.assertFalse(inter.match(fields_neg, (1, 1)))
        self.assertFalse(inter.match(fields, (-1, -1)))
        self.assertTrue(inter.match(fields, (1, 1)))
        self.assertFalse(inter.match(fields_neg, (-1, -1)))

    def test_difference_match(self):
        loc = nc.inport(1,1)
        field = nc.Header('srcmac', 1)
        diff = loc - field

        self.assertTrue(diff.match(fields_neg, (1, 1)))
        self.assertFalse(diff.match(fields, (-1, -1)))
        self.assertFalse(diff.match(fields, (1, 1)))
        self.assertFalse(diff.match(fields_neg, (-1, -1)))

    def test_nary_union(self):
        loc1 = nc.inport(1, 1)
        loc2 = nc.inport(2, 2)
        loc3 = nc.inport(3, 3)

        union = nc.nary_union([loc1, loc2, loc3])
        self.assertTrue(union.match(blank_packet, (1,1)))
        self.assertTrue(union.match(blank_packet, (2,2)))
        self.assertTrue(union.match(blank_packet, (3,3)))
        self.assertFalse(union.match(blank_packet, (-1,-1)))

    def test_nary_intersection(self):
        field1 = nc.Header('srcmac', 1)
        field2 = nc.Header('dstmac', 2)
        field3 = nc.Header('ethtype', 3)

        inter = nc.nary_intersection([field1, field2, field3])
        self.assertTrue(inter.match(
            nc.Packet({'srcmac':1, 'dstmac':2, 'ethtype':3}), (1,1)))
        self.assertFalse(inter.match(
            nc.Packet({'srcmac':-1, 'dstmac':2, 'ethtype':3}), (1,1)))
        self.assertFalse(inter.match(
            nc.Packet({'srcmac':1, 'dstmac':-2, 'ethtype':3}), (1,1)))
        self.assertFalse(inter.match(
            nc.Packet({'srcmac':2, 'dstmac':2, 'ethtype':-3}), (1,1)))

class TestAction(unittest.TestCase):
    def test_modify_returns_new_packet(self):
        action = nc.Action(1, ports=[1], modify={})
        modified, (switch, port) = action.modify_packet(full_packet)
        self.assertEqual(full_packet, modified)
        self.assertFalse(full_packet is modified)

    def test_modify(self):
        action = nc.Action(1, ports=[1], modify={'srcmac':-1, 'ethtype':-3})
        expected = copy.copy(fields)
        expected['srcmac'] = -1
        expected['ethtype'] = -3

        modified, (switch, port) = action.modify_packet(full_packet)
        self.assertEqual(expected, modified.fields)

    def test_get_physical(self):
        switch_map = {1: 100}
        port_map = {(1,2): (100, 200), (1,3): (100, 300)}
        action = nc.Action(1, ports=[2,3])
        expected = nc.Action(100, ports=[200, 300])

        phys = action.get_physical_rep(port_map, switch_map)

        self.assertEqual(expected, phys)

class TestPolicy(unittest.TestCase):
    def test_prim_phys(self):
        switch_map = {1: 100}
        port_map = {(1,2): (100, 200), (1,3): (100, 300)}
        pred = nc.inport(1, 2)
        expected_pred = nc.inport(100, 200)

        action = nc.Action(1, ports=[2])
        expected_action = nc.Action(100, ports=[200])

        policy = pred |then| action
        expected_policy = expected_pred |then| expected_action

        phys_policy = policy.get_physical_rep(port_map, switch_map)
        self.assertEqual(expected_policy, phys_policy)

    def test_prim_actions(self):
        header = exact_header
        actions = [nc.Action(1), nc.Action(2, ports=[2])]

        policy = header |then| actions

        self.assertEqual([], policy.get_actions(nega_packet, (1, 2)))
        self.assertEqual(actions, policy.get_actions(full_packet, (1,2)))

if __name__ == '__main__':
    unittest.main()