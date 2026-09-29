# Source mappings

OFT 4.9.0 does not import short tags from `.hs` files. These native Markdown
items declare the mapping to symbols in the captured `Main.hs`. Source changes
must keep the mapping accurate; the structural checker does not resolve Haskell
symbols. Execution evidence is for the whole command.

## Expiration implementation
`impl~session-expiration~1`

The `expired` function in [Main.hs](Main.hs) implements the expiration decision.

Covers:
 - `req~expiration~1`

## Expiration postcondition
`utest~expiration-postcondition~1`

The `postcondition` property in [Main.hs](Main.hs) compares the result with the
specified rule over generated signed timestamps and positive timeouts. Explicit
examples check equality and expiration after the boundary.

Covers:
 - `req~expiration~1`

## Exact expiration boundary
`utest~expiration-boundary~1`

The `boundary` property in [Main.hs](Main.hs) checks one tick before expiration
and equality, over generated timestamps and positive timeouts.

Covers:
 - `req~expiration~1`

## Timestamp translation
`utest~expiration-shift~1`

The `translation` property in [Main.hs](Main.hs) shifts both timestamps by the
same generated amount and checks that the decision is preserved.

Covers:
 - `req~expiration~1`
