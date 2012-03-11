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
# /updates/Slice.py                                                            #
# Data structure to represent virtual network slices                           #
################################################################################
"""Data structure to represent virtual network slices and related tools."""

def is_injective(mapping):
    """Determine if a mapping is injective.

    ARGS:
        mapping: map to check

    RETURNS:
        True if mapping is injective, False otherwise
    """
    pass

def policy_is_total(edge_policy, topo):
    """Determine if an edge policy covers all edge ports.
    
    ARGS:
        edge_policy:  collection of (edge_port, predicate) pairs that represents
            a slice's policy for ingress edges
        topo: NXTopo to which edge_policy applies

    RETURNS:
        True if all the edges in topo have a matching predicate, False
            otherwise.
    """
    pass

class Slice:
    """Data structure to represent virtual network slices."""
    def __init__(self, logical_topology, physical_topology, node_map, port_map,
                 edge_policy):
        """Create a Slice.

        ARGS:
            logical_topology: NXTopo object representing the logical topology
                that this slice uses
            physical_topology: NXTopo this slice will run on top of
            node_map: mapping from nodes in the logical topology to nodes in
                the physical topology, must be injective
            port_map: mapping from ports in the logical topology to ports in the
                physical topology, must be injective
            edge_policy: set of (edge_port, predicate) pairs, only packets
                entering the edge port that satisfy the predicate will be allowed to
                pass
        """
        self.l_topo = logical_topology
        self.p_topo = physical_topology
        self.node_map = node_map
        self.port_map = port_map
        self.edge_policy = edge_policy
        assert self.validate()

    def validate(self):
        """Check sanity conditions on this slice.

        Validates the following concerns:
        * All nodes in the logical topology are mapped by node_map
        * All ports in the logical topology are mapped by port_map
        * node_map is injective
        * port_map is injective
        * every edge port in the logical topology is associated with a predicate
        """
        return (self.l_topo.nodes == self.node_map.keys() and
                self.l_topo.edges == self.port_map.keys() and
                is_injective(self.node_map) and
                is_injective(self.port_map) and
                policy_is_total(self.edge_policy, self.l_topo))