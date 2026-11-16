#
#  SpaceMissionStudio
#
#  Licensor: 0h3xn4 (https://github.com/0h3xn4)
#
#  Licensed under the EUPL
#
#  SPDX-License-Identifier: EUPL-1.2
#
#  The European Union Public Licence v. 1.2 is in the files LICENSE
#  (English) and LICENSE.de (German) of the SpaceMissionStudio folder and
#  of every package. Third-party components, each under its own licence,
#  are listed in THIRD_PARTY_NOTICES.
#
#
#
#
"""Mission operations planning: from targets, passes and requests to a
conflict-free, time-tagged plan per spacecraft, flown in the simulation
to check it, exported as operations products
(docs/developer/operations-planning-design.md).

The planner is numpy only; Basilisk is used only to propagate (through
the existing service) and to fly the plan (``execution``)."""
