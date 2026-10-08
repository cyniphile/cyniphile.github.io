# /// script
# requires-python = ">=3.13"
# dependencies = [
#   "marimo>=0.25.0",
#   "numpy",
#   "plotly",
# ]
# ///
import marimo

__generated_with = "0.25.0"
app = marimo.App(app_title="Entropy Is Just Counting")


@app.cell
def _():
    import marimo as mo

    return (mo,)


@app.cell
def _():
    import math

    import numpy as np
    from plotly import graph_objs as go
    from plotly.subplots import make_subplots

    TEAL = "#1b7f86"  # the blog's link color
    ORANGE = "#e07a1f"
    GRAY = "#6f6f6f"
    PLOTLY_CONFIG = {"responsive": True, "displayModeBar": False, "staticPlot": True}

    def style(fig, height):
        """The look that every figure in this post shares."""
        fig.update_layout(
            height=height,
            template="plotly_white",
            margin=dict(l=60, r=10, t=60, b=50),
            font=dict(size=13),
            legend=dict(x=0.99, y=0.99, xanchor="right", yanchor="top", bgcolor="rgba(255,255,255,0.85)"),
        )
        return fig

    def odds(log10_p):
        """A probability, given as its base-10 log, in words: "67%", "1 in 3,162", "1 in 3 × 10^829"."""
        if log10_p >= -2:
            return f"{10**log10_p:.0%}"
        if log10_p >= -6:
            return f"1 in {round(10**-log10_p):,}"
        exponent = math.floor(-log10_p)
        mantissa = round(10 ** (-log10_p - exponent))
        if mantissa == 10:
            mantissa, exponent = 1, exponent + 1
        if mantissa == 1:
            return f"1 in $10^{{{exponent}}}$"
        return f"1 in ${mantissa} \\times 10^{{{exponent}}}$"

    def log_omega(N, q):
        """The log of the number of ways to share q quanta among N particles, ln C(q+N-1, q).

        Computed with the log-gamma function, so it works for counts far too big for a float."""
        return math.lgamma(q + N) - math.lgamma(q + 1) - math.lgamma(N)

    return GRAY, ORANGE, PLOTLY_CONFIG, TEAL, go, log_omega, make_subplots, math, np, odds, style


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    # Entropy Is Just Counting (With Interactive Simulations)

    ## Why Read This Post?

    Entropy is about as close as physics gets to the meaning of life. It's behind the arrow of time, it's why heat flows from hot to cold, and it's why you can't unscramble an egg. In Isaac Asimov's short story *The Last Question*, people spend the entire future of the universe asking an ever more powerful computer whether the rise of entropy can be reversed. Each time, the computer comes back with some version of "THERE IS AS YET INSUFFICIENT DATA FOR A MEANINGFUL ANSWER."

    But ask what entropy actually *is*, and you'll usually get a hand-wave about "disorder."

    The surprise for me was that the core idea is more math than physics, and the math is mostly counting. That simplicity is a big part of why physicists trust the second law of thermodynamics so much. Simple means less room for error. Here's Arthur Eddington in 1928:

    > The law that entropy always increases—the Second Law of Thermodynamics—holds, I think, the supreme position among the laws of Nature.

    If your theory disagrees with it, he added, "there is nothing for it but to collapse in deepest humiliation." As we'll see, the law earns that spot because it's a statement about odds, and the odds are overwhelming.

    > **TODO (Luke):** Susskind quote here. Pull it from [his lectures](https://theoreticalminimum.com/courses/statistical-mechanics/2013/spring), not from memory.

    This post goes from particles bouncing around in a box to the **Boltzmann distribution**, the formula for how likely a particle is to be in a state with a given energy. Along the way we'll find out what entropy and temperature actually are. It's the foundation for free energy, which is where this series is headed.

    > Prerequisites: a little probability. Some calculus (logs and derivatives) helps, and I'll explain what we use as we go.
    >
    > The simulations are real Python. To poke at the code, open the [live notebook](/blog/entropy-is-counting/live/).
    """)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## A Box of Gas

    Picture a box of gas: thousands of particles bouncing off the walls and off each other. The collisions are *elastic*, meaning no energy is lost, it just gets passed around. The total energy in the box stays fixed.

    Each collision shuffles energy between two particles: one speeds up, the other slows down. So after lots of collisions, where does the energy end up? Does it even out, so every particle has about the same amount? Does it pile up on a few lucky particles?

    Let's simulate it. The box below has 20,000 particles moving in two dimensions. To keep things simple, the simulation doesn't track positions. Each round, it pairs every particle with a random partner, and each pair collides at a random angle. Every collision conserves momentum and energy exactly.

    We'll try two very different starts:

    1. Every particle has the same energy.
    2. One particle has *all* the energy, and everyone else is standing still.

    Drag the slider to run the collisions.
    """)
    return


@app.cell
def _(np):
    # The gas: 20,000 particles moving in 2D, all with mass 1. The average energy per particle
    # is 1, which for a 2D gas means kT = 1.
    N_GAS = 20_000
    ROUNDS = [0, 1, 2, 3, 4, 6, 8, 12, 16, 20, 25, 30, 40, 50]

    def collide(v, rng):
        """Pair every particle with a random partner, and have each pair collide elastically.

        In a pair's center-of-mass frame, an elastic collision just turns the relative velocity
        around: its length stays the same. So we keep the length and pick a new direction at
        random. That conserves momentum and energy exactly."""
        order = rng.permutation(len(v))
        a, b = order[0::2], order[1::2]
        center = (v[a] + v[b]) / 2
        speed = np.linalg.norm(v[a] - v[b], axis=1)
        angle = rng.uniform(0, 2 * np.pi, len(a))
        relative = speed[:, None] * np.column_stack([np.cos(angle), np.sin(angle)])
        v[a] = center + relative / 2
        v[b] = center - relative / 2

    def run_gas(start, seed):
        """Every particle's energy after each number of rounds in ROUNDS."""
        rng = np.random.default_rng(seed)
        if start == "equal":  # the same speed for everyone, in random directions: energy 1 each
            angle = rng.uniform(0, 2 * np.pi, N_GAS)
            v = np.sqrt(2) * np.column_stack([np.cos(angle), np.sin(angle)])
        else:  # one particle has all the energy, and the rest stand still
            v = np.zeros((N_GAS, 2))
            v[0, 0] = np.sqrt(2 * N_GAS)
        energies = {}
        for r in range(ROUNDS[-1] + 1):
            if r in ROUNDS:
                energies[r] = 0.5 * (v**2).sum(axis=1)
            if r < ROUNDS[-1]:
                collide(v, rng)
        return energies

    gas = {"equal": run_gas("equal", seed=1), "hog": run_gas("hog", seed=2)}
    return N_GAS, ROUNDS, gas


@app.cell
def _(ROUNDS, mo):
    rounds = mo.ui.slider(steps=ROUNDS, value=0, label="Collisions per particle")
    rounds
    return (rounds,)


@app.cell
def _(GRAY, N_GAS, ORANGE, PLOTLY_CONFIG, TEAL, gas, go, make_subplots, mo, np, rounds, style):
    _bin = 0.3  # (so the starting energy, exactly 1, sits in the middle of a bar, not on an edge)
    _edges = np.arange(0, 6 + _bin / 2, _bin)
    _centers = (_edges[:-1] + _edges[1:]) / 2
    _top = 0.35  # the y-axis stops here; a taller bar is cut off and labeled
    # The dashed curve: the share of particles per bar that e^(-E/kT) predicts, with kT = 1
    _x = np.linspace(0, 6, 121)
    _curve = 2 * np.sinh(_bin / 2) * np.exp(-_x)

    _fig = make_subplots(
        rows=2,
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.16,
        subplot_titles=["Everyone starts with the same energy", "One particle starts with all of it"],
    )
    for _row, _start in enumerate(["equal", "hog"], start=1):
        _share = np.histogram(gas[_start][rounds.value], _edges)[0] / N_GAS
        _fig.add_trace(
            go.Bar(
                x=_centers,
                y=np.minimum(_share, _top),
                width=_bin * 0.85,
                marker_color=TEAL,
                name="Simulation",
                showlegend=_row == 1,
            ),
            row=_row,
            col=1,
        )
        _fig.add_trace(
            go.Scatter(
                x=_x,
                y=_curve,
                mode="lines",
                line=dict(color=ORANGE, dash="dash", width=3),
                name="Mystery curve",
                showlegend=_row == 1,
            ),
            row=_row,
            col=1,
        )
        _tallest = int(_share.argmax())
        _fig.add_annotation(
            row=_row,
            col=1,
            x=_centers[_tallest] + 0.2,
            y=_top,
            xanchor="left",
            yanchor="top",
            text=f"↑ {round(_share[_tallest] * N_GAS):,} particles",
            showarrow=False,
            font=dict(color=GRAY, size=12),
            visible=bool(_share[_tallest] > _top),
        )
        _fig.update_yaxes(title_text="Share of particles", range=[0, _top], row=_row, col=1)
    _fig.update_xaxes(range=[0, 6], row=1, col=1)
    _fig.update_xaxes(title_text="Energy (1 = the average energy per particle)", range=[0, 6], row=2, col=1)
    style(_fig, 600)
    _fig.update_layout(margin=dict(t=100), legend=dict(orientation="h", x=0, y=1.1, xanchor="left", yanchor="bottom"))
    mo.ui.plotly(_fig, config=PLOTLY_CONFIG)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    A few things to notice:

    - The two starts couldn't be more different, but they end up in the same place.
    - That place isn't "everyone has the same energy." Most particles end up with less than the average, and a few end up with a lot more.
    - Once it gets there, it stays there. More collisions don't change the shape.
    - Both histograms land on the dashed orange line. What is that curve? Hold that thought; it's what the rest of this post is about.

    The one-particle start is fun to watch. For a while nothing seems to happen, because when two particles that are standing still collide, nothing changes. The energy spreads like a rumor: one particle tells another, those two tell two more, and so on, until everyone has heard.

    ### Energy and Temperature

    Two numbers describe our box.

    The **total energy** $E$ is the sum of every particle's kinetic energy, $\frac{1}{2}mv^2$. It's fixed: collisions only move it around.

    **Temperature** measures the *average* kinetic energy per particle. (My first guess was that temperature is the average *speed*. Close, but energy goes like $v^2$, so it's the average of $v^2$ that matters.) For a gas moving in two dimensions, like ours,

    $$
    \left\langle \tfrac{1}{2} m v^2 \right\rangle = kT
    $$

    The angle brackets mean "the average over all the particles." $T$ is the temperature in kelvins, and $k \approx 1.38 \times 10^{-23}$ J/K is **Boltzmann's constant**, a conversion factor between temperature and energy. (In three dimensions, the average is $\frac{3}{2}kT$.)

    So energy is a total, and temperature is an average. Put two identical boxes side by side: the energy doubles, but the temperature stays the same.

    For now, take "temperature measures average energy" as given. Later we'll see a deeper definition that it falls out of.

    ### Entropy, Version 1: Clausius

    In the 1850s and '60s, Rudolf Clausius was trying to understand steam engines. He found a quantity that never goes down, and in 1865 he named it **entropy**. His definition: if you slowly add a small amount of heat $dQ$ to something at temperature $T$, its entropy goes up by

    $$
    dS = \frac{dQ}{T}
    $$

    The **second law of thermodynamics** says that the total entropy of an isolated system never decreases.

    That's enough to explain why heat flows from hot to cold. Say a little heat $dQ$ leaves a hot object and goes into a cold one. The hot object's entropy drops by $dQ/T_{\text{hot}}$. The cold object's entropy rises by $dQ/T_{\text{cold}}$, which is bigger, because you're dividing by a smaller temperature. So the total goes up, and the second law allows it. Heat flowing the other way would make the total go down, so it never happens.

    This is tidy bookkeeping, but it doesn't say what entropy *is*. What's being measured? Why does it only go up? And why divide by $T$, of all things? To find out, we have to zoom in.
    """)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## Zooming In

    Forget the 20,000 particles. Zoom way in on just a dozen, few enough that we can count things.

    And there is something to count, because quantum mechanics says a particle's energy can't take just any value. It comes in discrete levels, like the rungs of a ladder. Instead of having "some" energy, a particle has exactly so many units of it.

    > **Is energy really quantized for a gas molecule?** Yes, for the same reason electron orbitals are. A molecule in a box is a quantum wave, and only waves that fit neatly inside the box are allowed. That gives a ladder of energies, $E_n = \frac{h^2 n^2}{8 m L^2}$, where $h$ is Planck's constant, $m$ is the molecule's mass, and $L$ is the size of the box. The rungs are just absurdly close together. For a nitrogen molecule in a one-meter box at room temperature, a typical molecule sits around rung 40 billion (counting along one direction), and neighboring rungs are about $2 \times 10^{-11}\,kT$ apart. That's why the energy looks continuous, and why classical physics works so well for gases. An electron trapped in a box the size of an atom (about $10^{-10}$ m) is the opposite: the gap between its first two rungs is thousands of $kT$.

    To make counting easy, we'll use a toy version: energy comes in identical chunks called **quanta**, and each particle holds a whole number of them. (A ladder with evenly spaced rungs is really a model of atoms vibrating in a solid, which physicists call an *Einstein solid*. A gas's rungs aren't evenly spaced, but the counting works the same way, and this version we can do with pencil and paper.)

    ### Counting Microstates

    A **microstate** is a complete list of how many quanta each particle has.

    Start tiny: 3 particles sharing 3 quanta. Here's every possibility:

    | Particle 1 | Particle 2 | Particle 3 |
    |:-:|:-:|:-:|
    | 3 | 0 | 0 |
    | 0 | 3 | 0 |
    | 0 | 0 | 3 |
    | 2 | 1 | 0 |
    | 2 | 0 | 1 |
    | 1 | 2 | 0 |
    | 0 | 2 | 1 |
    | 1 | 0 | 2 |
    | 0 | 1 | 2 |
    | 1 | 1 | 1 |

    Ten microstates.

    For bigger numbers there's a neat counting trick called *stars and bars*. Write each microstate as a row of quanta ($\bullet$) with dividers ($|$) between the particles: $\bullet\bullet|\bullet|$ means particle 1 has two quanta, particle 2 has one, and particle 3 has none. Every microstate is some arrangement of $q$ dots and $N - 1$ dividers, so counting microstates means counting the ways to choose which of the $q + N - 1$ spots hold the dots:

    $$
    \Omega(N, q) = \binom{q + N - 1}{q}
    $$

    The capital omega, $\Omega$, is the traditional symbol for the number of microstates. Check: $\Omega(3, 3) = \binom{5}{3} = 10$. ✓

    Fun fact: this formula is where quantum theory began. In 1900, Max Planck used it to count the ways of sharing energy among "resonators" when he worked out the spectrum of light from hot objects. He borrowed the trick from Boltzmann, who had chopped energy into chunks to count arrangements, then shrunk the chunks to zero at the end. Planck found that his formula only matched experiments if the chunks stayed a definite size, $\varepsilon = h\nu$. That chunk size is where Planck's constant got its meaning.

    Now for the one physical assumption in this whole post: **for a system on its own with a fixed total energy, every microstate is equally likely.** Collisions shuffle energy around at random without preferring any particular arrangement, so no arrangement is special. (It's called the *fundamental assumption of statistical mechanics*. It is an assumption, but it has held up spectacularly.)

    That means the chance of anything is just the number of microstates where it's true, divided by the total. Try it:
    """)
    return


@app.cell
def _(mo):
    n_particles = mo.ui.slider(2, 24, value=12, label="Particles")
    n_quanta = mo.ui.slider(2, 24, value=12, label="Quanta")
    mo.vstack([n_particles, n_quanta])
    return n_particles, n_quanta


@app.cell
def _(math, mo, n_particles, n_quanta, odds):
    _N, _q = n_particles.value, n_quanta.value
    _omega = math.comb(_q + _N - 1, _q)
    mo.md(
        f"**{_N} particles** sharing **{_q} quanta** can be arranged in **Ω = {_omega:,}** ways. "
        f"In {_N} of them, one particle holds all {_q} quanta. "
        f"So the chance that one particle has everything is **{odds(math.log10(_N / _omega))}**."
    )
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    With a dozen particles sharing a dozen quanta, there are more than a million microstates, and only 12 of them have one particle hogging everything. "It's unlikely that one particle has all the energy" isn't a vague intuition anymore. It's a count. Crank up the sliders and the odds get worse fast. For the 20,000 particles in our simulation, they're beyond astronomical. Nothing *forces* the energy away from the hog. There are just vastly more arrangements where it's shared.

    ### Entropy, Version 2: Boltzmann

    Ludwig Boltzmann's big idea was that entropy is the logarithm of the number of microstates:

    $$
    S = k \ln \Omega
    $$

    It's carved on his tombstone in Vienna (with a $W$ instead of an $\Omega$). Fittingly, it was Planck who first wrote it in this form, and who named $k$ after Boltzmann.

    Why a logarithm? Put two separate systems side by side. Each microstate of the first can go with each microstate of the second, so the counts *multiply*: $\Omega_{\text{total}} = \Omega_A \, \Omega_B$. But we'd like entropy to *add*, the way energy does, and logs turn products into sums: $\ln(\Omega_A \Omega_B) = \ln \Omega_A + \ln \Omega_B$. The $k$ is Boltzmann's constant again. It puts entropy in the same units as Clausius's.

    Is this really the same thing Clausius defined with his steam engines? It is. We need one more idea to see why, so stick a pin in that.

    > **Aside: Shannon entropy.** If you've done any machine learning, $\ln \Omega$ might look familiar. Claude Shannon defined the entropy of a probability distribution as $H = -\sum_i p_i \ln p_i$. If all $\Omega$ microstates are equally likely, each has $p_i = 1/\Omega$, and then $H = \ln \Omega$. So Boltzmann's entropy is Shannon's entropy of "which microstate are we in?", times $k$. Measured in bits (logs base 2), it's the number of yes/no questions you'd need to pin down the exact microstate. For a dozen particles sharing a dozen quanta, that's $\log_2 1{,}352{,}078 \approx 20.4$, so about 20 questions (21 to be sure).
    """)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## Two Boxes

    Now take two boxes. Box A has all the energy. Box B has none. Put them in contact, so they can trade quanta.

    Intuitively, the energy won't stay put in box A. It'll spread out. But how much ends up in each box, and how sure can we be? Let's count.

    Box A has $N_A$ particles, box B has $N_B$, and there are $q$ quanta in total. If box A holds $q_A$ of them, box B holds the rest, $q - q_A$. Each microstate of A can go with each microstate of B, so the number of microstates with that split is

    $$
    \Omega_A(q_A) \times \Omega_B(q - q_A)
    $$

    Every microstate is equally likely, so the chance of each split is proportional to its count.

    Below, box B has twice as many particles as box A, and there's one quantum per particle on average. All the energy starts in box A. The top panel is a simulation: at each step, a random particle hands one of its quanta (if it has any) to another random particle, in either box. The bottom panel is the exact count. Start with a dozen particles, then make the boxes bigger.
    """)
    return


@app.cell
def _(log_omega, math, np):
    BOX_A_SIZES = [1, 2, 4, 10, 30, 100, 300, 1000]  # box B always has twice as many particles
    SWEEPS = 40  # how long to run, in exchanges per particle

    def run_boxes(n, seed):
        """All the energy starts in box A: n particles with 3 quanta each. Box B has 2n particles
        and no quanta. At each step, a random particle (in either box) gives one quantum, if it
        has one, to another random particle. Returns box A's share of the energy over time."""
        rng = np.random.default_rng(seed)
        total = q = 3 * n
        quanta = [3] * n + [0] * (2 * n)
        steps = SWEEPS * total
        givers = rng.integers(total, size=steps).tolist()
        takers = rng.integers(total, size=steps).tolist()
        every = max(1, steps // 400)
        in_a, share = q, [1.0]
        for k in range(steps):
            g, t = givers[k], takers[k]
            if quanta[g] > 0:
                quanta[g] -= 1
                quanta[t] += 1
                in_a += (t < n) - (g < n)
            if (k + 1) % every == 0:
                share.append(in_a / q)
        time = np.arange(len(share)) * every / total
        return time, np.array(share)

    def split_counts(n):
        """For each share of the energy in box A: how many microstates of the two boxes have that
        split, relative to the most likely split. Also the base-10 log of the chance that box A has
        all of the energy."""
        q = 3 * n
        logs = np.array([log_omega(n, a) + log_omega(2 * n, q - a) for a in range(q + 1)])
        log10_all_in_a = (logs[-1] - log_omega(3 * n, q)) / math.log(10)
        return np.arange(q + 1) / q, np.exp(logs - logs.max()), log10_all_in_a

    boxes = {n: run_boxes(n, seed=5) for n in BOX_A_SIZES}  # a fixed seed: the same page on every visit
    return BOX_A_SIZES, SWEEPS, boxes, split_counts


@app.cell
def _(BOX_A_SIZES, mo):
    box_size = mo.ui.slider(steps=BOX_A_SIZES, value=4, label="Particles in box A")
    box_size
    return (box_size,)


@app.cell
def _(ORANGE, PLOTLY_CONFIG, SWEEPS, TEAL, box_size, boxes, go, make_subplots, mo, odds, split_counts, style):
    _n = box_size.value
    _time, _share = boxes[_n]
    _x, _relative, _log10_all_in_a = split_counts(_n)
    _keep = _relative > 1e-4  # leave out splits too rare to see
    _fig = make_subplots(
        rows=2,
        cols=1,
        vertical_spacing=0.24,
        subplot_titles=["Box A's share of the energy (simulation)", "Arrangements for each split (exact count)"],
    )
    _fig.add_trace(go.Scatter(x=_time, y=_share, mode="lines", line=dict(color=TEAL, width=2)), row=1, col=1)
    _fig.add_trace(
        go.Scatter(x=_x[_keep], y=_relative[_keep], mode="lines", line=dict(color=TEAL, width=2)), row=2, col=1
    )
    _dots = _keep.sum() <= 40  # dots for each split only while there are few enough to see
    _fig.add_trace(
        go.Scatter(
            x=_x[_keep] if _dots else [],
            y=_relative[_keep] if _dots else [],
            mode="markers",
            marker=dict(color=TEAL, size=7),
        ),
        row=2,
        col=1,
    )
    _fig.add_hline(y=1 / 3, line=dict(color=ORANGE, dash="dash", width=2), row=1, col=1)
    _fig.add_vline(x=1 / 3, line=dict(color=ORANGE, dash="dash", width=2), row=2, col=1)
    _fig.update_xaxes(title_text="Time (exchanges per particle)", range=[0, SWEEPS], row=1, col=1)
    _fig.update_yaxes(title_text="Share in A", range=[0, 1.02], row=1, col=1)
    _fig.update_xaxes(title_text="Box A's share of the energy", range=[0, 1], row=2, col=1)
    _fig.update_yaxes(title_text="Relative count", range=[0, 1.05], row=2, col=1)
    _fig.update_layout(showlegend=False)
    mo.vstack(
        [
            mo.md(
                f"Box A: **{_n:,}** particle{'' if _n == 1 else 's'}. Box B: **{2 * _n:,}** particles. "
                f"**{3 * _n:,}** quanta, all starting in box A. "
                f"The chance that a random arrangement has all of the energy in box A: **{odds(_log10_all_in_a)}**."
            ),
            mo.ui.plotly(style(_fig, 600), config=PLOTLY_CONFIG),
        ]
    )
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    The dashed orange lines mark one third: box A's share of the particles, and its average share of the energy. (With small boxes the most likely split sits a bit below that, and the peak closes in on one third as the boxes grow.)

    With a dozen particles (4 in A, 8 in B), the energy sloshes all over the place, and the count in the bottom panel is a broad hump: lots of different splits are reasonably likely. Even all of the energy back in box A is only a 1-in-3,000 long shot. Now make the boxes bigger. The energy drops toward one third and then hovers around it, and the wiggles shrink as the boxes grow. The bottom panel shows why: almost all the microstates pile up around that one split, and the pile gets narrower as the boxes grow. Leaving all the energy in box A isn't forbidden. It's just hopelessly outnumbered: with 1,000 particles in box A, its chance is roughly 1 in $3 \times 10^{829}$. A real box of gas has more like $10^{23}$ particles.

    **That's the second law.** The entropy of the current split, $k \ln(\Omega_A \Omega_B)$, climbs as the energy drifts toward the peak, because there are overwhelmingly more ways for energy to be spread out than bunched up. Nothing pushes the energy out of box A. Random shuffling just almost never finds its way back. So when Clausius's second law says entropy *never* goes down, it really means "almost never," with odds like the ones above.

    ### What Temperature Really Is

    Where exactly is the peak? At the top of a hill, the ground is flat: moving one quantum from A to B doesn't change the count (to first order). In terms of logs, which are easier to work with, that's

    $$
    \frac{d \ln \Omega_A}{d q_A} = \frac{d \ln \Omega_B}{d q_B}
    $$

    Read $d \ln \Omega / dq$ as "how fast the number of arrangements grows as you add quanta." Since it's the log that's growing, it's a *percentage* growth rate: $d \ln \Omega$ is the same as $d\Omega / \Omega$. So the boxes settle down where adding a quantum to either one would grow its count by the same percentage.

    Something that's equal between two boxes once they've settled down... that's what a thermometer measures! So here's the deep definition of temperature:

    $$
    \frac{1}{kT} = \frac{d \ln \Omega}{dE}
    $$

    where $E = q\varepsilon$ is the energy and $\varepsilon$ is the energy of one quantum. A cold box's count grows by a big *percentage* for each bit of energy you give it, and a hot box's count grows by a small one. So if box A is hotter than box B, moving a quantum from A to B shrinks A's count by a smaller percentage than it grows B's. The total count is the product $\Omega_A \Omega_B$, so it goes up. Heat flows from hot to cold because that's where the arrangements are.

    Does this match "temperature measures average energy" from before? For our toy we can work it out exactly. Adding one quantum multiplies the count by

    $$
    \frac{\Omega(N, q+1)}{\Omega(N, q)} = \frac{q + N}{q + 1}
    $$

    (write out the binomials and almost everything cancels). With lots of quanta and lots of particles, that's about $1 + N/q$, so

    $$
    \frac{d \ln \Omega}{dq} \approx \ln\left(1 + \frac{N}{q}\right) \approx \frac{N}{q}
    $$

    where the last step holds when each particle has many quanta ($q \gg N$). Plug that into the definition of temperature:

    $$
    \frac{1}{kT} = \frac{1}{\varepsilon}\frac{d \ln \Omega}{dq} \approx \frac{N}{q \varepsilon} = \frac{N}{E}
    $$

    Flip it over:

    $$
    \frac{E}{N} \approx kT
    $$

    The average energy per particle is $kT$, the same rule as our 2D gas, but now derived instead of assumed. That's no coincidence: like our evenly spaced ladder, a 2D gas has the same number of states in every slice of energy. (In 3D there are more states at higher energies, and the average comes out to $\tfrac{3}{2}kT$.) And when the particles hold only a few quanta each, that last approximation breaks down. That's where quantum effects show up.

    ### Back to Clausius

    Multiply both sides of the temperature definition by $k$, and remember that $S = k \ln \Omega$:

    $$
    \frac{dS}{dE} = \frac{1}{T} \quad\Longrightarrow\quad dS = \frac{dE}{T}
    $$

    When the energy comes in as heat, $dE = dQ$, and this is *exactly* Clausius's $dS = dQ/T$. The steam-engine entropy and the counting entropy are the same thing. And the $1/T$ isn't arbitrary: it's the exchange rate between energy and arrangements. Clausius was counting microstates all along. He just didn't know it.
    """)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## The Boltzmann Distribution

    One last move. Make box B enormous (call it a *reservoir*), and shrink box A down to a single particle. What's the chance that our particle holds $n$ quanta?

    If our particle has $n$ quanta, the reservoir has the rest. Our particle's microstate is pinned down, so the number of microstates is just the reservoir's count:

    $$
    P(n) \propto \Omega_B(q - n)
    $$

    Now look at what each quantum costs. Taking one quantum away from the reservoir lowers $\ln \Omega_B$ by $d \ln \Omega_B / dq = \varepsilon / kT$. That's just the definition of temperature, applied to the reservoir. And since the reservoir is enormous, a few quanta don't change its temperature, so every quantum costs the same:

    $$
    \ln \Omega_B(q - n) \approx \ln \Omega_B(q) - n\frac{\varepsilon}{kT}
    $$

    Exponentiate both sides, and write the particle's energy as $E = n\varepsilon$:

    $$
    P(E) \propto e^{-E/kT}
    $$

    That's the **Boltzmann distribution**. Every quantum our particle takes multiplies its probability by the same factor, $e^{-\varepsilon/kT}$, because it costs the reservoir the same fraction of its arrangements. High energies aren't forbidden, just exponentially expensive.

    Strictly, this is the chance of each *state* with energy $E$. Our particle has exactly one state per rung of the ladder, so here it's also the chance of each energy. Hold on to that distinction; it'll matter in a minute.

    We can check it against an exact count. Below, our particle shares quanta with all the others, with one quantum per particle on average. The ratio from earlier, $(q + N)/(q + 1)$, is about 2 when $q = N$, so $e^{-\varepsilon/kT} \approx 1/2$, and the Boltzmann distribution says the chance should halve with every quantum. Starting from $1/2$, so that all the chances add up to 1, that's $1/2, 1/4, 1/8, \dots$ (Notice that $kT$ here is about 1.44 quanta, not the average of 1. With only one quantum per particle, we're in the regime where "average energy $= kT$" breaks down.)
    """)
    return


@app.cell
def _(mo):
    n_total = mo.ui.slider(steps=[2, 3, 4, 6, 12, 25, 50, 100, 1000], value=12, label="Particles, counting ours")
    n_total
    return (n_total,)


@app.cell
def _(ORANGE, PLOTLY_CONFIG, TEAL, go, log_omega, math, mo, n_total, np, style):
    _N = n_total.value
    _q = _N  # one quantum per particle, on average
    _n = np.arange(9)
    # Exact: our particle holds n quanta, and the other N - 1 particles share the remaining q - n
    _exact = [math.exp(log_omega(_N - 1, _q - k) - log_omega(_N, _q)) if k <= _q else 0.0 for k in _n]
    _fig = go.Figure(
        [
            go.Bar(x=_n, y=_exact, marker_color=TEAL, name="Exact count"),
            go.Scatter(
                x=_n,
                y=0.5 ** (_n + 1),
                mode="lines+markers",
                line=dict(color=ORANGE, dash="dash", width=3),
                marker=dict(color=ORANGE, size=8),
                name="Boltzmann prediction",
            ),
        ]
    )
    _fig.update_layout(title=dict(text=f"{_N:,} particles sharing {_q:,} quanta", x=0.01))
    _fig.update_xaxes(title_text="Quanta held by our particle", dtick=1)
    _fig.update_yaxes(title_text="Chance", range=[0, 0.55])
    mo.ui.plotly(style(_fig, 420), config=PLOTLY_CONFIG)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    With 2 particles, the "reservoir" is a single particle, and every split is equally likely: no exponential at all. By a dozen it's already close. By a thousand you can't tell them apart. The Boltzmann distribution is what you get when the rest of the world is big.

    ### Remember the Mystery Curve?

    Scroll back up to the gas simulation. The dashed line that both histograms settled onto is $e^{-E/kT}$, the Boltzmann distribution, with $kT$ equal to the average energy per particle. Each gas particle plays the part of our single particle, and the other 19,999 are its reservoir. The collisions didn't know anything about counting. They just shuffled energy around at random, without favoring any arrangement, and almost every arrangement looks like that curve.

    > **Why a 2D gas?** Remember that $e^{-E/kT}$ is the chance of each *state*. To get the chance of each energy, you also have to count how many states have that energy. So count the possible velocities in a thin slice of energy. In 2D they form a ring that gets longer as the speed grows, but thinner in the same proportion, so every slice of energy holds the same number of states, just like our ladder. That's why the histogram is a pure exponential. In 3D they form a spherical shell whose area grows faster than it thins, so the number of states grows like $\sqrt{E}$, and you get $\sqrt{E}\,e^{-E/kT}$: the famous Maxwell–Boltzmann distribution.

    ## Outro

    Here's the whole post in four lines:

    - **Entropy** counts microstates: $S = k \ln \Omega$.
    - **The second law** is a statement about counting: there are overwhelmingly more ways for energy to be spread out, so that's where you'll find it.
    - **Temperature** is set by how fast the count grows as you add energy (fast growth means cold): $1/kT = d \ln \Omega / dE$.
    - **The Boltzmann distribution** is what a big reservoir's counting does to a small system: the chance of each state is proportional to $e^{-E/kT}$.

    One thing we skated past: a small system in contact with a reservoir gets pulled two ways. The reservoir pulls it toward low energy, since every quantum it takes costs the reservoir arrangements. Its own count pulls it toward states that have lots of arrangements. (That's why the 3D Maxwell–Boltzmann curve has a hump.) Which pull wins? That tug-of-war is called **free energy**, and it's the subject of the next post.

    ## References

    - [Statistical Mechanics](https://theoreticalminimum.com/courses/statistical-mechanics/2013/spring), Leonard Susskind's *Theoretical Minimum* lectures (Stanford, 2013). The first four lectures follow almost exactly this arc: entropy, temperature, maximizing entropy, and the Boltzmann distribution.
    - *An Introduction to Thermal Physics*, Daniel V. Schroeder (2000). Chapter 2 has two Einstein solids trading energy, with the microstate counts worked out. The two-box setup here comes from there.
    - [The Principles of Statistical Mechanics](https://www.feynmanlectures.caltech.edu/I_40.html), *The Feynman Lectures on Physics*, Vol. I, Chapter 40. Feynman gets to the Boltzmann factor a completely different way: from how the air thins out as you go up in the atmosphere.
    - *The Nature of the Physical World*, Arthur Eddington (1928). The source of the quote at the top.
    - [The Last Question](https://en.wikipedia.org/wiki/The_Last_Question), Isaac Asimov (1956). Short, and worth your time.
    """)
    return


if __name__ == "__main__":
    app.run()
