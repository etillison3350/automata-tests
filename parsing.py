from collections.abc import Iterable, Sequence
from typing import NamedTuple, TypeVar

import itertools

from nfa import NFA


_T = TypeVar('_T')


class _OperatorParams(NamedTuple):
    id: int
    num_args: int
    precedence: int
    suffix: bool
    commutative: bool


_operators = {
    None: _OperatorParams(0, 2, 2, False, False),
    '|': _OperatorParams(1, 2, 1, False, True),
    '*': _OperatorParams(2, 1, 3, True, False),
    '+': _OperatorParams(3, 1, 3, True, False),
    '?': _OperatorParams(4, 1, 3, True, False),

    '(': _OperatorParams(5, 0, 0, False, False),
    ')': _OperatorParams(6, 0, 0, False, False),

    # '[': _OperatorParams(7, 0, False),
    # ']': _OperatorParams(8, 0, False)
}
_operators.update({op.id: op for _, op in _operators.items()})


def parse_regex(regex: str) -> list[int | str]:
    """Parse the given input regex into postfix notation using the shunting-yard algorithm"""

    stack = []
    postfix_output = []
    concatenate_next = False
    current_pos = 0
    while current_pos < len(regex):
        sym = regex[current_pos]
        if sym == '\\':
            current_pos += 1
            sym += regex[current_pos]
            escape = True
        else:
            escape = False
        if concatenate_next and (sym == '(' or sym not in _operators):
            sym = None
        else:
            current_pos += 1

        op_param = _operators[sym] if sym in _operators else None
        if sym == '(':
            stack.append(op_param.id)
            if regex[current_pos] == '?':
                current_pos += 2
                if regex[current_pos - 1] == '<':
                    if regex[current_pos] not in '!=':
                        while regex[current_pos - 1] != '>':
                            current_pos += 1

            concatenate_next = False
        elif sym == ')':
            while stack[-1] != _operators['('].id:
                postfix_output.append(stack.pop())
            stack.pop()
            concatenate_next = True
        elif sym in _operators:
            while len(stack) > 0 and (type(stack[-1]) != int or _operators[stack[-1]].precedence > op_param.precedence):
                postfix_output.append(stack.pop())
            if op_param.suffix:
                postfix_output.append(op_param.id)
                concatenate_next = True
            else:
                stack.append(op_param.id)
                concatenate_next = False
        else:
            postfix_output.append(sym[1:] if escape else sym)
            concatenate_next = True

    while len(stack) > 0:
        postfix_output.append(stack.pop())

    return postfix_output


def construct_string(postfix: list[int | str]) -> str:
    if len(postfix) == 0:
        return ''
    stack = []
    for sym in postfix:
        if type(sym) == int:
            args = []
            for _ in range(_operators[sym].num_args):
                arg, op = stack.pop()
                if op is not None and _operators[op].precedence < _operators[sym].precedence:
                    arg = '(' + arg + ')'
                args.append(arg)
            if sym == 0:
                stack.append((args[1] + args[0], sym))
            elif sym == 1:
                stack.append((args[1] + '|' + args[0], sym))
            elif sym == 2:
                stack.append((args[0] + '*', sym))
            elif sym == 3:
                stack.append((args[0] + '+', sym))
            elif sym == 4:
                stack.append((args[0] + '?', sym))
        else:
            stack.append((sym, None))
    if len(stack) != 1:
        raise ValueError
    return stack[0][0]


def parse_regex_as_string(regex: str) -> str:
    return construct_string(parse_regex(regex))


def construct_nfa(postfix: list[int | str]) -> NFA[str]:
    if len(postfix) == 0:
        return NFA(frozenset((0,)), frozenset(), {}, 0, 0)

    stack = []
    for sym in postfix:
        if type(sym) == int:
            syms = list(stack.pop() for _ in range(_operators[sym].num_args))
            if sym == 0:
                stack.append(syms[1] + syms[0])
            elif sym == 1:
                stack.append(syms[1] | syms[0])
            elif sym == 2:
                stack.append(syms[0].star())
            elif sym == 3:
                stack.append(syms[0].plus())
            elif sym == 4:
                stack.append(syms[0].opt())
        else:
            stack.append(NFA(frozenset((0, 1)),
                             frozenset() if sym is None else frozenset((sym,)),
                             {(0, sym): frozenset((1,))},
                             0,
                             1))
    if len(stack) != 1:
        raise ValueError
    return stack[0]


def parse_regex_as_nfa(regex: str) -> NFA[str]:
    return construct_nfa(parse_regex(regex))


def postfix_rip_combiner(pre_t: _T | tuple[_T | int, ...],
                         star: Iterable[_T | tuple[_T | int, ...]],
                         post_t: _T | tuple[_T | int, ...]) -> tuple[_T | int, ...]:
    if isinstance(pre_t, tuple):
        pre = list(pre_t)
    elif pre_t == '':
        pre = []
    else:
        pre = [pre_t]
    if isinstance(post_t, tuple):
        post = list(post_t)
    elif post_t == '':
        post = []
    else:
        post = [post_t]
    repeat = []
    for loop in star:
        if isinstance(loop, tuple):
            repeat = _op_if_nonempty('|', list(loop), repeat)
        elif loop != '':
            repeat = _op_if_nonempty('|', [loop], repeat)

    loop_pre, loop_post = pre == repeat, post == repeat
    if loop_pre and loop_post:
        new_sym = _op_if_nonempty('+', repeat)
    elif loop_pre:
        new_sym = _op_if_nonempty(None, _op_if_nonempty('+', repeat), post)
    elif loop_post:
        new_sym = _op_if_nonempty(None, pre, _op_if_nonempty('+', repeat))
    else:
        new_sym = _op_if_nonempty(None, pre, _op_if_nonempty('*', repeat), post)

    return tuple(new_sym)


def postfix_union_combiner(options: Iterable[_T | tuple[_T | int, ...]]) -> tuple[_T | int, ...]:
    union = []
    optional = False
    for loop in options:
        if isinstance(loop, tuple):
            if loop == ():
                optional = True
            else:
                union = _op_if_nonempty('|', union, list(loop))
        elif loop == '':
            optional = True
        else:
            union = _op_if_nonempty('|', union, [loop])

    if optional:
        union = _op_if_nonempty('?', union)

    return tuple(union)


def postfix_edge_label_func(syms: Iterable[_T]) -> str:
    label = construct_string(list(postfix_union_combiner(syms)))
    return '\u03B5' if label == '' else label


_duplicate_quantifiers = {
    (2, 2): 2,
    (2, 3): 2,
    (2, 4): 2,
    (3, 2): 2,
    (3, 3): 3,
    (3, 4): 2,
    (4, 2): 2,
    (4, 3): 2,
    (4, 4): 4,
}


def _op_if_nonempty(op: None | str | int, *args: list[_T | int], simplify: bool = True) -> list[_T | int]:
    op_param = _operators[op]
    rv = []
    num_operands = 0
    for arg in sorted(args, key=len) if op_param.commutative else args:
        if len(arg) > 0:
            rv.extend(arg)
            num_operands += 1
    if num_operands == 0:
        return []
    if num_operands != op_param.num_args and (num_operands - 1) % (op_param.num_args - 1) != 0:
        raise ValueError('Invalid number of operands')
    num_operators = 1 if op_param.num_args == 1 else (num_operands - 1) // (op_param.num_args - 1)

    op_id = op_param.id
    if simplify and (rv[-1], op_param.id) in _duplicate_quantifiers:
        op_id = _duplicate_quantifiers[(rv[-1], op_param.id)]
        rv.pop()

    for _ in range(num_operators):
        rv.append(op_id)
    return rv


def enumerate_regexes(alphabet: Iterable[str],
                      length: int,
                      allow_empty_str=False) -> list[list[str | int]]:
    return _enumerate_regexes(alphabet, length, allow_empty_str, {})


def _enumerate_regexes(alphabet: Iterable[str],
                       length: int,
                       allow_empty_str: bool,
                       memo: dict[int, list[list[str | int]]]) -> list[list[str | int]]:
    if length in memo:
        return memo[length]
    if length == 0:
        memo[0] = [['']] if allow_empty_str else []
        return memo[0]
    retval = []
    if length == 1:
        retval.extend([sym] for sym in alphabet)
    for op in (None, '|', '*'):
        n_args = _operators[op].num_args
        allow_empty = op == '|' and allow_empty_str
        for comb in itertools.combinations(range(length) if allow_empty else range(1, length - 1), n_args - 1):
            part_lists = (_enumerate_regexes(alphabet, hi - lo, allow_empty_str, memo)
                          for lo, hi in itertools.pairwise((0, *comb, length - 1)))
            for parts in itertools.product(*part_lists):
                retval.append(sum(parts, start=[]) + [_operators[op].id])
    memo[length] = retval
    return retval

