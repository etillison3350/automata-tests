from __future__ import annotations
from collections.abc import Iterable, Sequence
from typing import Callable, Generic, Optional, TypeVar

from collections import defaultdict
import graphviz

import nfa

_T = TypeVar('_T')


class DFA(Generic[_T]):
    def __init__(self,
                 states: frozenset[int],
                 alphabet: frozenset[_T],
                 transitions: dict[tuple[int, _T], int],
                 start_state: int,
                 final_states: frozenset[int]):
        if start_state not in states:
            raise ValueError('Start state must be in states')
        if any(state not in states for state in final_states):
            raise ValueError('All final states must be in states')

        self.states = states
        self.alphabet = alphabet
        self.transitions = transitions.copy()
        self.start_state = start_state
        self.final_states = final_states

    def minimize(self) -> DFA[_T]:
        reachable_states, reachable_finals = set(), set()
        if self.start_state in self.final_states:
            reachable_finals.add(self.start_state)
        else:
            reachable_states.add(self.start_state)

        worklist = [self.start_state]
        while len(worklist) > 0:
            curr = worklist.pop()
            for sym in self.alphabet:
                if (curr, sym) in self.transitions:
                    dst = self.transitions[(curr, sym)]
                    if dst not in reachable_states and dst not in reachable_finals:
                        if dst in self.final_states:
                            reachable_finals.add(dst)
                        else:
                            reachable_states.add(dst)
                        worklist.append(dst)

        partitions = [reachable_states, reachable_finals]
        final_states = {1}
        worklist = [0, 1]
        while len(worklist) > 0:
            curr_part = partitions[worklist.pop()]
            for sym in self.alphabet:
                for index in range(len(partitions)):
                    part = partitions[index]
                    to_curr, not_to_curr = [], []
                    for state in part:
                        if (state, sym) in self.transitions and self.transitions[(state, sym)] in curr_part:
                            to_curr.append(state)
                        else:
                            not_to_curr.append(state)
                    if len(to_curr) == 0 or len(not_to_curr) == 0:
                        continue
                    partitions[index] = to_curr
                    partitions.append(not_to_curr)
                    if index in final_states:
                        final_states.add(len(partitions) - 1)
                    if index in worklist or len(to_curr) > len(not_to_curr):
                        worklist.append(len(partitions) - 1)
                    else:
                        worklist.append(index)
        state_map = {}
        for index, states in enumerate(partitions):
            for state in states:
                state_map[state] = index
        transitions = {}
        for index, states in enumerate(partitions):
            for state in states:
                for sym in self.alphabet:
                    if (state, sym) in self.transitions:
                        transitions[(index, sym)] = state_map[self.transitions[(state, sym)]]

        return DFA(frozenset(range(len(partitions))),
                   self.alphabet,
                   transitions,
                   state_map[self.start_state],
                   frozenset(final_states))

    def to_nfa(self):
        max_s = max(self.states)
        final_state = max_s + 1
        states = self.states.union((final_state,))
        transitions = {key: frozenset((val,)) for key, val in self.transitions.items()}
        for state in self.final_states:
            transitions[(state, '')] = frozenset((final_state,))
        return nfa.NFA(states, self.alphabet, transitions, self.start_state, final_state)

    def accept(self, string: Sequence[_T]) -> bool:
        current_state = self.start_state
        for sym in string:
            if not (current_state, sym) in self.transitions:
                return False
            current_state = self.transitions[(current_state, sym)]
        return current_state in self.final_states

    def dump(self, directory, name='dfa', edge_label: Optional[Callable[[Iterable[_T]], str]] = None):
        if edge_label is None:
            edge_label = _default_edge_label_function
        dot = graphviz.Digraph(name, graph_attr={'rankdir': 'LR'}, node_attr={'shape': 'circle'})
        for state in self.states:
            dot.node(str(state), shape=('doublecircle' if state in self.final_states else 'circle'))
        edges = defaultdict(list)
        for key, dst in self.transitions.items():
            src, sym = key
            edges[(src, dst)].append(sym)
        for edge, syms in edges.items():
            src, dst = edge
            label = edge_label(syms)
            dot.edge(str(src), str(dst), label=label)
        dot.node('', shape='none')
        dot.edge('', str(self.start_state))
        dot.render(directory=directory)


def _default_edge_label_function(syms: Iterable[_T]) -> str:
    return ','.join(sorted('\u03B5' if sym == '' else str(sym) for sym in syms))
