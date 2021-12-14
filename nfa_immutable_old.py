from __future__ import annotations
from collections.abc import Iterable, Sequence
from typing import Any, Callable, Generic, Optional, TypeVar

from collections import defaultdict
import graphviz

import dfa

_S = TypeVar('_S')
_T = TypeVar('_T')


class NFA(Generic[_T]):
    def __init__(self,
                 states: frozenset[int],
                 alphabet: frozenset[_T],
                 transitions: dict[tuple[int, _T | str], frozenset[int]],
                 start_state: int,
                 final_state: int):
        if start_state not in states:
            raise ValueError('Start state must be in states')
        if final_state not in states:
            raise ValueError('Final state must be in states')

        self.states = states
        self.alphabet = alphabet
        self.transitions = transitions.copy()
        self.start_state = start_state
        self.final_state = final_state

    def __add__(self, other: NFA[_S]) -> NFA[_S | _T]:
        alphabet = self.alphabet.union(other.alphabet)
        max_s = max(self.states)
        min_o = min(other.states)
        corr = max_s - min_o + 1
        states = self.states.union(state + corr for state in other.states if state != other.start_state)
        transitions = self.transitions.copy()
        for key, dst in other.transitions.items():
            src, sym = key
            new_key = (self.final_state if src == other.start_state else src + corr, sym)
            new_dst = frozenset(self.final_state if state == other.start_state else state + corr for state in dst)
            transitions[new_key] = new_dst
        start_state = self.start_state
        final_state = other.final_state + corr
        return NFA(states, alphabet, transitions, start_state, final_state)

    def __or__(self, other: NFA[_S]) -> NFA[_S | _T]:
        alphabet = self.alphabet.union(other.alphabet)
        max_s = max(self.states)
        min_o = min(other.states)
        corr = max_s - min_o + 1
        states = self.states.union(state + corr for state in other.states
                                   if state != other.start_state and state != other.final_state)
        transitions = self.transitions.copy()
        mapper = lambda s: self.final_state if s == other.final_state else (self.start_state if s == other.start_state else s + corr)
        for key, dsts in other.transitions.items():
            src, sym = key
            new_src = mapper(src)
            if (new_src, sym) in transitions:
                transitions[(new_src, sym)] = transitions[(new_src, sym)].union(frozenset(mapper(dst) for dst in dsts))
            else:
                transitions[(new_src, sym)] = frozenset(mapper(state) for state in dsts)
        return NFA(states, alphabet, transitions, self.start_state, self.final_state)

    def star(self) -> NFA[_T]:
        max_s = max(self.states)
        start_state = max_s + 1
        final_state = max_s + 2
        states = self.states.union((start_state, final_state))
        transitions = self.transitions.copy()
        transitions[(start_state, '')] = frozenset((self.start_state, final_state))
        if (self.final_state, '') in transitions:
            transitions[(self.final_state, '')] = transitions[(self.final_state, '')].union((self.start_state, final_state))
        else:
            transitions[(self.final_state, '')] = frozenset((self.start_state, final_state))
        return NFA(states, self.alphabet, transitions, start_state, final_state)

    def plus(self) -> NFA[_T]:
        max_s = max(self.states)
        start_state = max_s + 1
        final_state = max_s + 2
        states = self.states.union((start_state, final_state))
        transitions = self.transitions.copy()
        transitions[(start_state, '')] = frozenset((self.start_state,))
        if (self.final_state, '') in transitions:
            transitions[(self.final_state, '')] = transitions[(self.final_state, '')].union((self.start_state, final_state))
        else:
            transitions[(self.final_state, '')] = frozenset((self.start_state, final_state))
        return NFA(states, self.alphabet, transitions, start_state, final_state)

    def opt(self) -> NFA[_T]:
        transitions = self.transitions.copy()
        if (self.start_state, '') in transitions:
            transitions[(self.start_state, '')] = transitions[(self.start_state, '')].union((self.final_state,))
        else:
            transitions[(self.start_state, '')] = frozenset((self.final_state,))
        return NFA(self.states, self.alphabet, transitions, self.start_state, self.final_state)

    def __sub__(self, other):
        return self.rip(other)

    def rip(self,
            state: int,
            safe: bool = False,
            combiner: Optional[Callable[[_S | _T, Iterable[_S | _T], _S | _T], _S]] = None) -> Optional[NFA[_S | _T]]:
        if combiner is None:
            combiner = _default_rip_combiner
        if state == self.start_state or state == self.final_state:
            raise ValueError('Cannot rip the start or final state')
        states = self.states.difference((state,))
        new_syms = set()
        outgoing_transitions, self_loops = dict(), set()
        for key, dsts in self.transitions.items():
            src, sym = key
            if src == state:
                if state in dsts:
                    if len(dsts) > 1:
                        outgoing_transitions[sym] = dsts.difference((state,))
                    if sym != '':
                        self_loops.add(sym)
                else:
                    outgoing_transitions[sym] = dsts
        transitions = {}
        for key, dsts in self.transitions.items():
            src, sym = key
            if src == state:
                continue

            if state in dsts:
                for out_sym, out_dsts in outgoing_transitions.items():
                    if safe:
                        if sym != '' and out_sym != '':
                            return None
                        new_sym = out_sym if sym == '' else sym
                        if (src, new_sym) in transitions:
                            transitions[(src, new_sym)] = transitions[(src, new_sym)].union(out_dsts)
                        else:
                            transitions[(src, new_sym)] = out_dsts

                    else:
                        new_sym = combiner(sym, self_loops, out_sym)

                        if (src, new_sym) in transitions:
                            transitions[(src, new_sym)] = transitions[(src, new_sym)].union(out_dsts)
                        else:
                            if new_sym != '':
                                new_syms.add(new_sym)
                            transitions[(src, new_sym)] = out_dsts
                dsts = dsts.difference((state,))
            if len(dsts) > 0:
                if key in transitions:
                    transitions[key] = transitions[key].union(dsts)
                else:
                    transitions[key] = dsts
        return NFA(states, self.alphabet.union(new_syms), transitions, self.start_state, self.final_state)

    def union_edges(self, combiner: Optional[Callable[[Iterable[_S | _T]], _S]] = None) -> NFA[_T | str]:
        if combiner is None:
            combiner = _default_union_combiner
        edges = defaultdict(set)
        for key, dsts in self.transitions.items():
            src, sym = key
            for dst in dsts:
                edges[(src, dst)].add(sym)
        transitions = {}
        alphabet = set()
        for edge, syms in edges.items():
            src, dst = edge
            new_sym = combiner(syms)
            if new_sym != '':
                alphabet.add(new_sym)
            if (src, new_sym) in transitions:
                transitions[(src, new_sym)] = transitions[(src, new_sym)].union((dst,))
            else:
                transitions[(src, new_sym)] = frozenset((dst,))
        return NFA(self.states, frozenset(alphabet), transitions, self.start_state, self.final_state)

    def renumber_states(self) -> NFA[_T]:
        if len(self.states.intersection(range(len(self.states)))) == 0:
            return self

        state_map = dict(zip(self.states, range(len(self.states))))
        transitions = {}
        for key, dsts in self.transitions:
            src, sym = key
            transitions[(state_map[src], sym)] = frozenset(state_map[dst] for dst in dsts)
        return NFA(frozenset(range(len(self.states))),
                   self.alphabet,
                   transitions,
                   state_map[self.start_state],
                   state_map[self.final_state])

    def eps_closure(self, state: int) -> set[int]:
        retval = set()
        if (state, '') not in self.transitions:
            return retval
        worklist = set(self.transitions[(state, '')])
        while len(worklist) > 0:
            curr = worklist.pop()
            retval.add(curr)
            if (curr, '') in self.transitions:
                for st in self.transitions[(curr, '')]:
                    if st not in retval:
                        worklist.add(st)
        return retval

    def next_states(self, current_state: int, sym: _T, incl_eps=False) -> set[int]:
        if sym not in self.alphabet:
            return set()

        retval = set()
        for state in (current_state, *self.eps_closure(current_state)):
            if (state, sym) in self.transitions:
                for next_state in self.transitions[(state, sym)]:
                    retval.add(next_state)
                    if incl_eps:
                        retval.update(self.eps_closure(next_state))
        return retval

    def accept(self, string: Sequence[_T]) -> bool:
        return self._accept(string, 0, self.start_state)

    def _accept(self, string: Sequence[_T], start_index: int, current_state: int) -> bool:
        if start_index == len(string):
            return current_state == self.final_state or self.final_state in self.eps_closure(current_state)
        return any(self._accept(string, start_index + 1, state)
                   for state in self.next_states(current_state, string[start_index]))

    def to_dfa(self, complete=False) -> dfa.DFA[_T]:
        eps_memo = {self.start_state: self.eps_closure(self.start_state).union((self.start_state,))}
        state_list: list[frozenset[int]] = [frozenset(eps_memo[self.start_state])]
        transitions = {}
        worklist = [0]
        while len(worklist) > 0:
            current_state = worklist.pop()

            if len(state_list[current_state]) == 0:
                for sym in self.alphabet:
                    transitions[(current_state, sym)] = current_state
                continue

            for sym in self.alphabet:
                result_states = set()
                for state in state_list[current_state]:
                    if (state, sym) in self.transitions:
                        result_states.update(self.transitions[(state, sym)])
                next_state = set()
                for state in result_states:
                    if state not in eps_memo:
                        eps_memo[state] = self.eps_closure(state).union((state,))
                    next_state.update(eps_memo[state])
                if not complete and len(next_state) == 0:
                    continue
                next_frozen = frozenset(next_state)
                if next_state in state_list:
                    transitions[(current_state, sym)] = state_list.index(next_frozen)
                else:
                    transitions[(current_state, sym)] = len(state_list)
                    worklist.append(len(state_list))
                    state_list.append(next_frozen)
        final_states = frozenset(i for i, states in enumerate(state_list) if self.final_state in states)
        return dfa.DFA(frozenset(range(len(state_list))), self.alphabet, transitions, 0, final_states)

    def degree(self, state: int) -> int:
        in_degree = sum(True for dst in self.transitions.values() if dst == state)
        out_degree = sum(True for sym in self.alphabet if (state, sym) in self.transitions)
        return in_degree + out_degree

    def in_out_sets(self, state: int) -> tuple[set[tuple[int, _T]], set[tuple[int, _T]]]:
        in_set = set()
        out_set = set()
        for key, dsts in self.transitions.items():
            src, sym = key
            if src == state:
                out_set.update((dst, sym) for dst in dsts)
            if state in dsts:
                in_set.add(key)
        return in_set, out_set

    def dump(self, directory: str, name='nfa', edge_label: Optional[Callable[[Iterable[_T]], str]] = None):
        if edge_label is None:
            edge_label = _default_edge_label_function
        dot = graphviz.Digraph(name, graph_attr={'rankdir': 'LR'}, node_attr={'shape': 'circle'})
        for state in self.states:
            dot.node(str(state), shape=('doublecircle' if state == self.final_state else 'circle'))
        edges: dict[tuple[int, int], set[_T]] = defaultdict(set)
        for key, dsts in self.transitions.items():
            src, sym = key
            for dst in dsts:
                edges[(src, dst)].add(sym)
        for edge, syms in edges.items():
            src, dst = edge
            label = edge_label(syms)
            dot.edge(str(src), str(dst), label=label)
        dot.node('', shape='none')
        dot.edge('', str(self.start_state))
        dot.render(directory=directory)


def _default_rip_combiner(a: str | _T, b: Iterable[str | _T], c: str | _T) -> str:
    pre, post = str(a), str(c)
    repeat = '|'.join(str(sym) for sym in b)
    loop_pre, loop_post = pre == repeat, post == repeat
    if loop_pre and loop_post:
        new_sym = '' if repeat == '' else '(' + repeat + ')+'
    elif loop_pre:
        new_sym = post if repeat == '' else '(' + repeat + ')+' + post
    elif loop_post:
        new_sym = pre if repeat == '' else pre + '(' + repeat + ')+'
    else:
        new_sym = pre + ('' if repeat == '' else '(' + repeat + ')*') + post
    return new_sym


def _default_union_combiner(syms: Iterable[str | _T]) -> str:
    new_sym = ''
    optional = False
    for sym in syms:
        if sym == '':
            optional = True
        elif new_sym == '':
            new_sym = str(sym)
        else:
            new_sym += '|' + str(sym)
    if optional and new_sym != '':
        return '(' + new_sym + ')?'
    else:
        return new_sym


def _default_edge_label_function(syms: Iterable[_T]) -> str:
    return ','.join(sorted('\u03B5' if sym == '' else str(sym) for sym in syms))
