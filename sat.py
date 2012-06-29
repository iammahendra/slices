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
# /slices/sat.py                                                               #
# Sat conversion and solving for netcore.                                      #
################################################################################
"""Sat conversion and solving for netcore.

ONLY CHECK FOR UNSAT UNLESS YOU'RE MARK

No observations yet.
"""

from z3.z3 import And, Or, Not, Implies, Function, ForAll
from z3.z3 import Consts, Solver, unsat, set_option, Ints
from netcore import HEADERS
import netcore as nc

from util import fields_of_policy

set_option(pull_nested_quantifiers=True)

from sat_core import nary_or, nary_and
from sat_core import HEADER_INDEX, Packet, switch, port, vlan
from sat_core import forwards, forwards_with

def transfer(topo, p_out, p_in):
    """Build constraint for moving p_out to p_in across an edge."""
    options = []
    for s1, s2 in topo.edges():
        p1 = topo.node[s1]['ports'][s2]
        p2 = topo.node[s2]['ports'][s1]
        # Need both directions because topo.edges() only gives one direction for
        # undirected graphs.
        constraint1 = And(And(switch(p_out) == s1, port(p_out) == p1),
                          And(switch(p_in) == s2, port(p_in) == p2))
        constraint2 = And(And(switch(p_out) == s2, port(p_out) == p2),
                          And(switch(p_in) == s1, port(p_in) == p1))
        options.append(constraint1)
        options.append(constraint2)
    forward = nary_or(options)

    # We also need to ensure that the rest of the packet is the same.  Without
    # this, packet properties can change in flight.
    header_constraints = []
    for f in HEADERS:
        if f is not 'switch' and f is not 'port':
            header_constraints.append(
                    HEADER_INDEX[f](p_out) == HEADER_INDEX[f](p_in))
    # header_constraints is never empty
    return And(forward, nary_and(header_constraints))

def explain(model, packet, headers):
    """Build {field: value} from model, packet and {field: function}."""
    properties = {}
    for f, v in headers.items():
        prop = model.evaluate(v(packet))
        # This is dirty, but this seems to be the only way to tell if
        # this value is determined or not
        if 'as_long' in dir(prop):
            properties[f] = int(prop.as_long())
        else: # Value not determined
            pass
    return properties

# TODO(astory): make sure this is rigorous.  I think it might have holes in it.
def equivalent(policy1, policy2):
    """Determine if policy1 is equivalent to policy2 under equality.

    Note that this is unidirectional, it only asks if the packets that can go
    into policy1 behave the same under policy1 as they do under policy2.
    """
    p1_in, p1_out = Consts('p1_in p1_out', Packet)
    p2_in, p2_out1, p2_out2 = Consts('p2_in p2_out1 p2_out2', Packet)
    s = Solver()
    # There are two components to this.  First, we want to ensure that if p1
    # forwards a packet, p2 also forwards it
    constraint = Implies(forwards(policy1, p1_in, p1_out),
                         forwards(policy2, p1_in, p1_out))
    # Second, we want to ensure that if p2 forwards a packet, and it's a packet
    # that p1 can forward, that p2 only forwards it in ways that p1 does.
    constraint = And(constraint,
                     Implies(And(forwards(policy2, p2_in, p2_out1),
                                 forwards(policy1, p2_in, p2_out2)),
                             forwards(policy1, p2_in, p2_out1)))
    # We want to check for emptiness, so our model gives us a packet back
    s.add(Not(constraint))

    if s.check() == unsat:
        return None
    else:
#       explanations = [str(explain(s.model(), p, HEADER_INDEX))
#                       for p in (p1_in, p1_out, p2_in, p2_out1, p2_out2)]
        return (s.model(), (p1_in, p1_out, p2_in, p2_out1, p2_out2),
                HEADER_INDEX)

def not_empty(policy):
    """Determine if there are any packets that the policy forwards.

    RETURNS:
        None if not forwardable.
        (model, (p_in, p_out), HEADERS) if forwardable.
    """
    p_in, p_out = Consts('p_in p_out', Packet)
    s = Solver()
    s.add(forwards(policy, p_in, p_out))
    if s.check() == unsat:
        return None
    else:
        return (s.model(), (p_in, p_out), HEADER_INDEX)

def compiled_correctly(orig, result):
    """Determine if result is a valid compilation of orig.

    Performs the following tests:
    O is the original policy
    R is the resulting policy
    ~ means equivalent up to vlans

    No lost behaviors:
    p -O-> p' => \exists q, q' . p ~ q /\ p' ~ q' /\ q -R-> q'

    No new behaviors:
    p -R-> p' => \exists q, q' . p ~ q /\ p' ~ q' /\ q -O-> q'

    RETURNS: True or False.  For models and diagnostics use no_new_behaviors and
    no_lost_behaviors.
    """
    return (simulates(orig, result) is None and
            simulates(result, orig) is None)

def simulates(a, b, field='vlan'):
    """Determine if b simulates a up to field."""
    p, pp = Consts('p pp', Packet)
    v, vv = Ints('v vv')

    solv = Solver()

    solv.add(And(forwards(a, p, pp),
             ForAll([v, vv], Not(forwards_with(b, p, {field: v},
                                                  pp, {field: vv})),
                                               patterns=[v + vv])))
    if solv.check() == unsat:
        return None
    else:
#       print solv.check()
#       print solv.model()
        return solv.model(), (
                              p, pp
                              ), HEADER_INDEX

def isolated(topo, policy1, policy2):
    """Determine if policy1 is isolated from policy2.

    RETURNS: True or False
    """
    return isolated_model(topo, policy1, policy2) is None

def isolated_diagnostic(topo, policy1, policy2):
    """Determine if policy1 is isolated from policy2.

    RETURNS: The empty string if they are isolated, or a diagnostic string
        detailing what packets will break isolation if they are not.
    """

    solution = isolated_model(topo, policy1, policy2)
    if solution is None:
        return ''
    else:
        (model, (p1, p2, p3, p4), hs) = solution
        properties = {}
        for p in (p1, p2, p3, p4):
            properties[str(p)] = explain(model, p, hs)
    return ('%s\n'
            '---policy1--->\n'
            '%s\n'
            '---topology-->\n'
            '%s\n'
            '---policy2--->\n'
            '%s'
            % (properties[str(p1)], properties[str(p2)],
               properties[str(p3)], properties[str(p4)]))

def isolated_model(topo, policy1, policy2):
    """Determine if policy1 can produce a packet that goes to policy2.

    RETURNS: None if the policies are isolated
             (model, (pkt1, pkt2, pkt3, pkt4), HEADER_INDEX) if they are not

    The idea here is that if

    \exists pkt1, pkt2, pkt3, pkt4 . P1(pkt1, pkt2) and
                                     transfer(pkt2, pkt3) and
                                     P2(pkt3, pkt4)

    is inhabited, then they're not isolated.

    If you want to get back the problematic packets, evaluate the HEADER_INDEX
    functions in the model on the packets.
    """
    pkt1, pkt2, pkt3, pkt4 = Consts('pkt1 pkt2 pkt3 pkt4', Packet)
    s = Solver()
    s.add(forwards(policy1, pkt1, pkt2))
    s.add(transfer(topo, pkt2, pkt3))
    s.add(forwards(policy2, pkt3, pkt4))

    if s.check() == unsat:
        return None
    else:
        return (s.model(), (pkt1, pkt2, pkt3, pkt4), HEADER_INDEX)