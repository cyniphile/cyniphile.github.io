# /// script
# requires-python = ">=3.13"
# dependencies = [
#   "altair",
#   "numpy",
#   "pandas",
#   "scipy",
#   "plotly",
# ]
# ///
import marimo

__generated_with = "0.19.6"
app = marimo.App(app_title="Intro to Gaussian Process Regression")


@app.cell
def _():
    import marimo as mo

    return (mo,)


@app.cell
def _():
    # @title
    import numpy as np
    import pandas as pd
    import scipy as sp
    from plotly import graph_objs as go

    np.random.seed(42)
    return go, np, pd, sp


@app.cell
def _(go):
    # Helper function to create Plotly heatmaps (replaces seaborn.heatmap)
    def plotly_heatmap(data, title="", xticklabels=None, yticklabels=None, annot=False):
        """Create a Plotly heatmap figure."""
        if hasattr(data, 'values'):
            z = data.values
            x = list(data.columns) if xticklabels is None else xticklabels
            y = list(data.index) if yticklabels is None else yticklabels
        else:
            z = data
            x = xticklabels if xticklabels is not None else list(range(len(data[0])))
            y = yticklabels if yticklabels is not None else list(range(len(data)))

        # Convert to strings so Plotly treats them as categorical (equal-sized squares)
        x = [str(val) for val in x]
        y = [str(val) for val in y]

        fig = go.Figure(data=go.Heatmap(
            z=z,
            x=x,
            y=y,
            colorscale='Viridis',
            showscale=True,
            text=z if annot else None,
            texttemplate='%{text:.2f}' if annot else None,
            hovertemplate='x: %{x}<br>y: %{y}<br>value: %{z:.4f}<extra></extra>',
        ))
        fig.update_layout(
            title=title,
            xaxis=dict(side='bottom', type='category', constrain='domain'),
            yaxis=dict(autorange='reversed', type='category', scaleanchor='x', constrain='domain'),
            margin=dict(l=60, r=20, t=50, b=60),
        )
        return fig

    PLOTLY_CONFIG = {"responsive": True, "displayModeBar": False, "staticPlot": True}
    return plotly_heatmap, PLOTLY_CONFIG


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    # The First Blog Post You Should Read about Gaussian Processes (With Interactive Plots)

    ## Why Read This Post?
    Is this the 10th blog post you've read about Gaussian Processes and still don't quite understand them?

    When I set out to learn about "Gaussian Processes" (really Gaussian Process Regression), I ended up jumping around between many different resources and it took hours before the core idea hit me. This post should get you to **core idea in ~30 minutes using interactive plots**.

    After that, I'd encourage you to read the references at the end for more detail and rigor. They'll now be more digestible.

    > Prerequisites: basic linear algebra and statistics.
    >
    > If you know python/numpy you might find it helpful to look at the code under the hood: open the [live notebook](/blog/gaussian-processes/live/).
    >
    """)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## Why Gaussian Process Regression?

    1. It's a non-linear regression model
    1. It also does built-in modeling of uncertainties (cool)

    The following plot from the sci-kit learn documentation shows the output of GP regression model. Note the beautifully curved uncertainty bands. Where does all this come from?

    ![](https://scikit-learn.org/0.17/_images/plot_gp_regression_001.png)
    """)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## GP Regression: The One Line Definition
    Turns out GP regression can be described in one (somewhat loaded) line:

    **GP Regression: A Multivariate Gaussian Distribution over functions, conditioned on some training data.**

    Hmm. Maybe not so terrible? But how does this connect to the idea of "a nonlinear regression that models uncertainty"?

    Let's unpack this definition bit by bit, starting with "distribution over functions".
    """)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## Prequel: Distributions over Functions

    We all know linear regression. Given some data, we assume it has the form $y = \beta_0 + \beta_1 x + \epsilon$. We have some data $x$ and $y$, and we want to find the $\hat{\beta_0}$ and $\hat{\beta_1}$ ("^" means "estimated") that describe a line of best fit. We can do this using OLS (ordinary least squares), and we end up with a linear function $f(x) = \hat{\beta_0} + \hat{\beta_1} x$, that for any $x$ gives us a prediction for $y$.

    Note that we don't model $\epsilon$; what if we want some notion of the uncertainty in our predictions?

    For example, look at the two plots below:
    """)
    return


@app.cell
def _(PLOTLY_CONFIG, go, mo, np):
    from plotly.subplots import make_subplots
    x_reg = np.linspace(-3, 3, 10)
    NOISE_VARIANCE = 1
    y_noise = x_reg + np.random.normal(0, NOISE_VARIANCE, 10)
    LOW_NOISE_VARIANCE = 0.1
    y_low_noise = x_reg + np.random.normal(0, LOW_NOISE_VARIANCE, 10)

    # Create regression plots with Plotly
    fig_reg = make_subplots(rows=1, cols=2, subplot_titles=("A", "B"))

    # Compute OLS for plot A
    slope_a, intercept_a = np.polyfit(x_reg, y_noise, 1)
    fit_y_a = slope_a * x_reg + intercept_a
    fig_reg.add_trace(go.Scatter(x=x_reg, y=y_noise, mode='markers', marker=dict(color='red'), showlegend=False), row=1, col=1)
    fig_reg.add_trace(go.Scatter(x=x_reg, y=fit_y_a, mode='lines', line=dict(color='red'), showlegend=False), row=1, col=1)

    # Compute OLS for plot B
    slope_b, intercept_b = np.polyfit(x_reg, y_low_noise, 1)
    fit_y_b = slope_b * x_reg + intercept_b
    fig_reg.add_trace(go.Scatter(x=x_reg, y=y_low_noise, mode='markers', marker=dict(color='blue'), showlegend=False), row=1, col=2)
    fig_reg.add_trace(go.Scatter(x=x_reg, y=fit_y_b, mode='lines', line=dict(color='blue'), showlegend=False), row=1, col=2)

    fig_reg.update_layout(height=350, margin=dict(l=40, r=20, t=40, b=40))
    mo.ui.plotly(fig_reg, config=PLOTLY_CONFIG)
    return LOW_NOISE_VARIANCE, NOISE_VARIANCE, x_reg, y_low_noise, y_noise


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    Even though the data on the left is much more noisy, both linear regressions model the data with the sample simple line. There's no measure of uncertainty. Let's try to add some.

    What if (just for fun) we assumed $\beta_0$ and $\beta_1$ were actually random variables, and that they are normally distributed with variance equal to the variance in the data? Then our linear regression equation would look like this:

    $$
    y = B_0 + B_1 x
    $$

    where we've converted our betas to random variables as follows:

    $$
    B_0 \sim N(\beta_0, \sigma^2)
    $$

    $$
    B_1 \sim N(\beta_1, \sigma^2)
    $$

    This reads "$B_0$ is a random variable distributed according to a Gaussian with mean $\beta_0$ and variance $\sigma^2$".
    We'll set $\sigma^2$ to be the variance of the data about the best fit line (the variance of the residuals). For the plots a and b above, then we'd have:

    $$
    y_a = B_{0a} + B_{1a} x
    $$

    $$
    y_b = B_{0b} + B_{1b} x
    $$

    where $B_0$ and $B_1$ are gaussians with variance equal to the variance of the residuals in each case: $\sigma^2_a$ and $\sigma^2_b$


    Now that the betas are random variables, let's sample from them, and plot the resulting lines:

    (Click the "New Sample" button below)
    """)
    return


@app.cell
def _(button, clear_button, get_fig_A, get_fig_B, mo):
    mo.vstack(
        [
            mo.hstack(
                [
                    mo.ui.plotly(
                        get_fig_A(),
                        config={"responsive": True, "displayModeBar": False, "staticPlot": True},
                    ),
                    mo.ui.plotly(
                        get_fig_B(),
                        config={"responsive": True, "displayModeBar": False, "staticPlot": True},
                    ),
                ]
            ),
            mo.hstack([button, clear_button]),
        ]
    )
    return


@app.cell
def _(
    LOW_NOISE_VARIANCE,
    NOISE_VARIANCE,
    go,
    mo,
    np,
    x_reg,
    y_low_noise,
    y_noise,
):
    # --- Initial parameters and helper function ---
    beta_0 = 0
    beta_1 = 1
    beta_1_1 = np.corrcoef(x_reg, y_noise)[0, 1] * np.std(y_noise) / np.std(x_reg)

    # Define color schemes for each plot
    colors_subplot1 = ["#ff4d4d", "#ff8533", "#ffcc00", "#ff6b6b", "#ff9966"]  # Warm colors
    colors_subplot2 = ["#4d4dff", "#33cc33", "#6666ff", "#00cccc", "#9933ff"]  # Cool colors

    def calculate_figure_height(num_traces):
        base_height = 300  # Base height for plot
        legend_rows = max(1, (num_traces - 2))  # For separate figures, initial trace count is 2
        legend_height = 40 + (legend_rows * 20)  # Base legend height + height per row
        return base_height + legend_height

    # --- Create two separate figures ---
    # Figure for Plot A (left figure)
    fig_A = go.Figure()
    fig_A.update_layout(
        title_text="A",
        height=calculate_figure_height(2),
        legend=dict(
            entrywidth=0.8,
            entrywidthmode="fraction",
            orientation="h",
            yanchor="bottom",
            y=-0.2,
            xanchor="center",
            x=0.4,
            bgcolor="white",
            bordercolor="LightGrey",
            borderwidth=0,
            itemsizing="constant",
            itemwidth=30,
            groupclick="toggleitem",
            valign="middle",
            xref="container",
            yref="container",
            traceorder="grouped",
            font=dict(size=10),
        ),
        autosize=True,
        margin=dict(l=4, r=3, t=80, b=10),
    )
    fig_A.update_xaxes(range=[-3, 3], fixedrange=True)

    # Figure for Plot B (right figure)
    fig_B = go.Figure()
    fig_B.update_layout(
        title_text="B",
        height=calculate_figure_height(2),
        legend=dict(
            entrywidth=0.8,
            entrywidthmode="fraction",
            orientation="h",
            yanchor="bottom",
            y=-0.2,
            xanchor="center",
            x=0.4,
            bgcolor="white",
            bordercolor="LightGrey",
            borderwidth=0,
            itemsizing="constant",
            itemwidth=30,
            groupclick="toggleitem",
            valign="middle",
            xref="container",
            yref="container",
            traceorder="grouped",
            font=dict(size=10),
        ),
        autosize=True,
        margin=dict(l=4, r=3, t=80, b=80),
    )
    fig_B.update_xaxes(range=[-3, 3], fixedrange=True)
    fig_B.update_yaxes(range=[-5, 5], fixedrange=True)

    # --- Add initial traces to each figure ---
    # Compute the lines for each plot
    line_A = x_reg * beta_1_1 + beta_0
    line_B = x_reg * beta_1 + beta_0

    # For Plot A: Noisy data and its fit
    scatter_A = go.Scatter(
        x=x_reg,
        y=y_noise,
        mode="markers",
        marker=dict(size=10, color=colors_subplot1[0]),
        name="Hi Noise Data",
        legendgroup="Plot A",
        showlegend=True,
    )
    line_A_trace = go.Scatter(
        x=x_reg,
        y=line_A,
        mode="lines",
        line=dict(color=colors_subplot1[1]),
        name="True Fit Hi Noise",
        legendgroup="Plot A",
        showlegend=True,
    )
    fig_A.add_trace(scatter_A)
    fig_A.add_trace(line_A_trace)

    # For Plot B: Low noise data and its fit
    scatter_B = go.Scatter(
        x=x_reg,
        y=y_low_noise,
        mode="markers",
        marker=dict(size=10, color=colors_subplot2[0]),
        name="Low Noise Data",
        legendgroup="Plot B",
        showlegend=True,
    )
    line_B_trace = go.Scatter(
        x=x_reg,
        y=line_B,
        mode="lines",
        line=dict(color=colors_subplot2[1]),
        name="True Fit Low Noise",
        legendgroup="Plot B",
        showlegend=True,
    )
    fig_B.add_trace(scatter_B)
    fig_B.add_trace(line_B_trace)

    # --- Save figures to state (using your mo.state API) ---
    get_fig_A, set_fig_A = mo.state(fig_A)
    get_fig_B, set_fig_B = mo.state(fig_B)

    # --- Callback functions ---
    def add_plot_to_fig(_):
        # Retrieve the current figures from state
        fig_A = get_fig_A()
        fig_B = get_fig_B()

        # Generate new random coefficients for both figures
        beta_0_rand = np.random.normal(beta_0, NOISE_VARIANCE, 1)
        beta_1_rand = np.random.normal(beta_1_1, NOISE_VARIANCE, 1)
        beta_0_rand2 = np.random.normal(beta_0, LOW_NOISE_VARIANCE, 1)
        beta_1_rand2 = np.random.normal(beta_1, LOW_NOISE_VARIANCE, 1)

        # Compute new line data for each plot
        line_data_A = x_reg * beta_1_rand + beta_0_rand
        line_data_B = x_reg * beta_1_rand2 + beta_0_rand2

        # Append new trace to Plot A (first figure)
        color_idx_A = len(fig_A.data) % len(colors_subplot1)
        fig_A.add_trace(
            go.Scatter(
                x=x_reg,
                y=line_data_A,
                mode="lines",
                line=dict(color=colors_subplot1[color_idx_A]),
                name=f"$B_{{0a}}: {beta_0_rand[0]:.1f}, B_{{1a}}: {beta_1_rand[0]:.1f}$",
                legendgroup="Plot A",
            )
        )

        # Append new trace to Plot B (second figure)
        color_idx_B = len(fig_B.data) % len(colors_subplot2)
        fig_B.add_trace(
            go.Scatter(
                x=x_reg,
                y=line_data_B,
                mode="lines",
                line=dict(color=colors_subplot2[color_idx_B]),
                name=f"$B_{{0b}}: {beta_0_rand2[0]:.1f}, B_{{1b}}: {beta_1_rand2[0]:.1f}$",
                legendgroup="Plot B",
            )
        )

        # Update each figure's height based on the new number of traces
        new_height_A = calculate_figure_height(len(fig_A.data))
        new_height_B = calculate_figure_height(len(fig_B.data))
        fig_A.update_layout(height=new_height_A)
        fig_B.update_layout(height=new_height_B)

        # Save the updated figures back into state
        set_fig_A(fig_A)
        set_fig_B(fig_B)

    def reset(_):
        # Retrieve the figures from state
        fig_A = get_fig_A()
        fig_B = get_fig_B()

        # Reset each figure to its initial two traces (scatter and original line)
        fig_A.data = fig_A.data[:2]
        fig_B.data = fig_B.data[:2]

        # Reset heights based on only the two traces
        fig_A.update_layout(height=calculate_figure_height(2))
        fig_B.update_layout(height=calculate_figure_height(2))

        set_fig_A(fig_A)
        set_fig_B(fig_B)

    # --- Create UI buttons ---
    button = mo.ui.button(value=0, on_click=add_plot_to_fig, label="New Sample", kind="success")
    clear_button = mo.ui.button(value=0, on_click=reset, label="Reset", kind="danger")
    return button, calculate_figure_height, clear_button, get_fig_A, get_fig_B


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    Each time you click the button, a new sample $\beta_0, \beta_1$ are drawn from the distributions of $B_0$ and $B_1$ (one set of betas for the noisy data on the left and one set for the less noisy on the right), and the corresponding lines are plotted.

    Notice what we've created: it's a distribution over _functions_. Each sample from  $y = B_0 + B_1 x$ is a different function $f(x)$. Also notice that as you sample more and more, the "spread" or uncertainty of the original fit becomes more and more apparent. You can also see that the uncertainty is higher in the noisier data.

    > This framework is just to develop for intuition for distributions over functions. For a more rigorous take, check out the bayesian linear regression section [here](https://gaussianprocess.org/gpml/chapters/RW.pdf#page=26&zoom=50,240,358).

    Returning to our original definition, we've checked off one core idea:

    **GP Regression: A Multivariate Gaussian <font color="#32a852">Distribution over functions</font>, conditioned on some training data.**

    What if we want to model a non-linear relationship? Now we're getting closer to the core idea of GPs. But of course, before we get to Gaussian processes, we have to talk about Gaussians.
    """)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    # Gaussians...and Multivariate Gaussians

    The Gaussian, the bell curve, the normal distribution, we've seen it before. It's defined by

    $$
    Y \sim N(\mu, \sigma^2)
    $$

    where $\mu$ is the mean and $\sigma^2$ is the variance. You can play around with the parameters of the distribution below. Each time you change the sliders, 10,000 samples are drawn from the distribution and plotted as a histogram.
    """)
    return


@app.cell
def _(get_fig_hist, mean_slider, mo, variance_slider):
    # 6. Lay out sliders and the figure
    mo.vstack(
        [
            mo.ui.plotly(
                get_fig_hist(),
                config={"responsive": True, "displayModeBar": False, "staticPlot": True},
            ),
            mo.hstack([mean_slider, variance_slider]),
        ]
    )
    return


@app.cell
def _(go, mo, np):
    # 1. Create the initial figure

    SIZE = 5000
    START = -10
    END = 10
    x = np.random.normal(0, 1, size=SIZE)
    hist_trace = go.Histogram(
        x=x,
        xbins=dict(start=START, end=END, size=0.1),  # whatever bin width you want
    )
    fig_hist = go.Figure(hist_trace)
    # 2. Store the figure and the slider states
    get_fig_hist, set_fig_hist = mo.state(fig_hist)
    fig_hist.update_layout(
        title="Normal Distribution Histogram<br>(µ=0.00, σ=1.00)",
        xaxis=dict(title="Value", range=[START, END], fixedrange=True),
        yaxis=dict(title="Count", range=[0, int(SIZE * 0.1)], fixedrange=True),
        margin=dict(l=4, r=3, t=80, b=10),
    )
    mean_state, set_mean_state = mo.state(0.0)
    variance_state, set_variance_state = mo.state(1.0)

    # 3. Function that updates the figure
    def update_histogram():
        fig = get_fig_hist()  # retrieve current figure from state
        x_new = np.random.normal(mean_state(), variance_state(), size=SIZE)
        fig.data[0].x = x_new
        fig.update_layout(
            title=(
                f"Normal Distribution Histogram<br>(µ={mean_state():.2f}, σ={variance_state():.2f})"
            )
        )
        set_fig_hist(fig)  # store the updated figure

    # 4. Handlers for slider changes
    def on_mean_change(m):
        set_mean_state(m)
        update_histogram()

    def on_variance_change(v):
        set_variance_state(v)
        update_histogram()

    # 5. Create the sliders
    mean_slider = mo.ui.slider(
        value=mean_state(), start=-5, stop=5, step=0.1, on_change=on_mean_change, label="Mean"
    )
    variance_slider = mo.ui.slider(
        value=variance_state(),
        start=0.1,
        stop=5,
        step=0.1,
        on_change=on_variance_change,
        label="Variance",
    )
    return get_fig_hist, mean_slider, variance_slider


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
 
    """)
    return


@app.cell
def _(mo):
    mo.md(r"""
    What about multivariate Gaussians? That is, a Gaussian distribution but with more than one variable. They are basically the same thing, but instead of having a single mean and variance, there's there's a mean vector and a covariance matrix.


    So while a single Gaussian is this:

    $$
    Y \sim N(\mu, \sigma^2)
    $$

    Where $\mu$ is the mean and $\sigma$ is the variance, a multivariate Gaussian is this:

    $$
    \textbf{Y} \sim N(\boldsymbol{\mu}, \Sigma)
    $$

    Where $\boldsymbol{\mu}$ is a vector of means, $\Sigma$ is a covariance matrix.

    $$
    \boldsymbol{\mu} = \begin{bmatrix}
    \mu_1 \\
    \mu_2 \\
    \vdots \\
    \mu_n
    \end{bmatrix},
    $$

    $$
    \qquad
    \Sigma = \begin{bmatrix}
    \sigma_{11} & \sigma_{12} & \dots & \sigma_{1n} \\
    \sigma_{21} & \sigma_{22} & \dots & \sigma_{2n} \\
    \vdots & \vdots & \ddots & \vdots \\
    \sigma_{n1} & \sigma_{n2} & \dots & \sigma_{nn}
    \end{bmatrix}.
    $$

    In the above expressions, $\mu_i$ is the mean of the $i$ th component of $\textbf{Y}$

    In this case when we sample from $\textbf{Y}$, we get a vector $\textbf{Y} = [Y_1, Y_2, \dots, Y_n]^T$,  instead of just a single value.
    """)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    Nothing too crazy right? Well, except that the multivariate normal distribution has a covariance _matrix_, not just a variance.

    In the covariance matrix we specify not only the variance of each variable, but also the covariance between each variable and every other. Each of the $n$ variables in a multivariate Gaussian can be correlated with each other. Below is an overhead view of a bunch of samples for a 2D multivariate Gaussian distribution. You can interactively change the covariance matrix to see how it affects the distribution.
    """)
    return


@app.cell
def _(alt, arr, df_orig, mat, mo, np, pd):
    try:
        x_sim = np.random.multivariate_normal(
            np.asarray(arr.value).reshape(-1), np.asarray(mat.value), 2500, check_valid="raise"
        )
        md = ""
    except ValueError as e:
        md = mo.md(
            f"""
            <div style="color: red; font-weight: bold;">
            Error: {e}.
            </div>
            """
        )
        x_sim = df_orig.values  # Fallback to original data if error occurs

    df_sim = pd.DataFrame({"x": x_sim[:, 0], "y": x_sim[:, 1]})

    min_x, max_x = -10, 10
    min_y, max_y = -10, 10

    chart_sim = (
        alt.Chart(df_sim)
        .mark_point()
        .encode(
            x=alt.X("x", scale=alt.Scale(domain=[min_x, max_x])),
            y=alt.Y("y", scale=alt.Scale(domain=[min_y, max_y])),
        )
        .properties(width=400, height=300)
        + alt.Chart(df_orig)
        .mark_point(color="gray")
        .encode(x="x", y="y")
        .properties(width=400, height=300)
    ).resolve_scale(x="shared", y="shared")

    mo.vstack([mo.hstack([arr, mat]), chart_sim, md], align="center")
    return


@app.cell
def _(mo, np):
    mat = mo.ui.matrix(np.eye(2), symmetric=True, step=0.1, min_value=0)
    arr = mo.ui.matrix([0.0, 0.0], step=0.1, min_value=0)
    return arr, mat


@app.cell
def _(np, pd):
    x_orig = np.random.multivariate_normal(
        np.array([0, 0]), np.array([[1, 0], [0, 1]]), 2500, check_valid="raise"
    )
    df_orig = pd.DataFrame({"x": x_orig[:, 0], "y": x_orig[:, 1]})
    return (df_orig,)


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    Note that if you change the diagonal elements, the variance of one or the other variable will change (look at the scale of axes). If you change the off-diagonal elements, the covariance between the two variables will change.

    You also probably saw that the matrix has to be symmetric and with positive diagonals. Why? Well think about what covariance is: its how two variables vary together. It doesn't make sense for Cov(X,Y) != Cov(Y,X). And it doesn't make sense for Cov(X,X) — that is, Var(X) — to be negative (you'll get an error if you try).

    Also note that while the combined joint distribution changes form, each of the individual distributions is still a Gaussian. That is to say, the distribution of $X_1$ is still a gaussian, and the distribution of $X_2$ is still a Gaussian. The only thing that changes is the covariance between the two variables.
    """)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## Gaussian Distribution Over Functions

    So far we've visualized a multivariate Gaussian of just two variables, but you can imagine taking this into many many dimensions. That is to say, many many Gaussian random variables that may or may not be correlated with each other according to some big covariance matrix.

    In order to think about more than two dimensions, we'll need to visualize our distributions differently. Let's start with a 1-D Gaussian. We'll draw samples from the distribution and plot them below:
    """)
    return


@app.cell
def _(go, mo, np):
    # 1) Create and store an initial figure in Marimo state
    initial_fig = go.Figure(
        data=[go.Scatter(mode="markers")],
        layout=go.Layout(title="Samples from a 1-D Gaussian Distribution"),
    )
    initial_fig.update_layout(
        margin=dict(l=4, r=3, t=80, b=10),
    )
    get_fig2, set_fig2 = mo.state(initial_fig)
    get_clicks2, set_clicks2 = mo.state(0)

    # 2) Define the callbacks that change the figure
    def add_sample(_):
        """Add a new random sample (1 point) to the figure."""
        fig = get_fig2()
        # We just stack data on top of the existing figure
        x = ["1"]
        y = np.random.normal(size=1)
        scatter = go.Scatter(x=x, y=y, mode="markers", name=f"Sample {get_clicks2()}")
        fig.add_trace(scatter)
        set_fig2(fig)  # update our global figure state
        set_clicks2(get_clicks2() + 1)

    def clear_data(_):
        """Clear all the data from the figure."""
        fig = get_fig2()
        fig.data = []
        set_fig2(fig)
        set_clicks2(0)

    # 3) Create the UI buttons, each calling its respective callback
    btn_new_sample = mo.ui.button(value=0, on_click=add_sample, label="New Sample", kind="success")
    btn_clear = mo.ui.button(value=get_clicks2(), on_click=clear_data, label="Clear", kind="danger")
    return btn_clear, btn_new_sample, get_fig2


@app.cell
def _(btn_clear, btn_new_sample, get_fig2, mo):
    mo.vstack(
        [
            mo.ui.plotly(
                get_fig2(), config={"responsive": True, "displayModeBar": False, "staticPlot": True}
            ),
            mo.hstack([btn_new_sample, btn_clear]),
        ]
    )
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    Each new sample is drawn from a normal distribution with mean 0 and variance 1.

    What if we want to sample from a multivariate normal distribution? Well, this time $\textbf{Y}$ is a _vector_ of random variables. If $\textbf{Y}$ is 2-d then $\textbf{Y} = [Y_1, Y_2]^T$, so each sample is a vector of two values which we'll plot each on their own part of the X-axis.
    """)
    return


@app.cell
def _(btn_clear_2d, btn_new_sample_2d, get_fig_2d, mo):
    mo.vstack(
        [
            mo.ui.plotly(
                get_fig_2d(),
                config={"responsive": True, "displayModeBar": False, "staticPlot": True},
            ),
            mo.hstack([btn_new_sample_2d, btn_clear_2d]),
        ]
    )
    return


@app.cell
def _(go, mo, np):
    # 2D Figure: "Samples from a 2-D Gaussian Distribution"
    init_scatter_2d = go.Scatter(mode="markers")
    init_layout_2d = go.Layout(title="Samples from a 2-D Gaussian Distribution")
    init_fig_2d = go.Figure(data=[init_scatter_2d], layout=init_layout_2d)
    init_fig_2d.update_layout(
        margin=dict(l=4, r=3, t=80, b=10),
    )

    get_fig_2d, set_fig_2d = mo.state(init_fig_2d)
    get_clicks_2d, set_clicks_2d = mo.state(0)

    def add_sample_2d(_):
        fig_2d = get_fig_2d()
        x_2d = ["1", "2"]
        y_2d = np.random.normal(size=2)
        new_scatter_2d = go.Scatter(
            x=x_2d, y=y_2d, mode="markers", name=f"Sample {get_clicks_2d()}"
        )
        fig_2d.add_trace(new_scatter_2d)
        set_fig_2d(fig_2d)
        set_clicks_2d(get_clicks_2d() + 1)

    def clear_data_2d(_):
        fig_2d = get_fig_2d()
        fig_2d.data = []
        set_fig_2d(fig_2d)
        set_clicks_2d(0)

    btn_new_sample_2d = mo.ui.button(
        value=0, on_click=add_sample_2d, label="New Sample", kind="success"
    )
    btn_clear_2d = mo.ui.button(
        value=get_clicks_2d(), on_click=clear_data_2d, label="Clear", kind="danger"
    )
    return btn_clear_2d, btn_new_sample_2d, get_fig_2d


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    So now each time we sample from a bivariate normal distribution, we get a vector of two numbers, which we plot as two connected points. Now let's look at a 3-D Gaussian,  $\textbf{Y}_{3D} = [Y_1, Y_2, Y_3]^T$,
    """)
    return


@app.cell
def _(btn_clear_3d, btn_new_sample_3d, get_fig_3d, mo):
    mo.vstack(
        [
            mo.ui.plotly(
                get_fig_3d(),
                config={"responsive": True, "displayModeBar": False, "staticPlot": True},
            ),
            mo.hstack([btn_new_sample_3d, btn_clear_3d]),
        ]
    )
    return


@app.cell
def _(go, mo, np):
    # 3D Figure: "Samples from a 3-D Gaussian Distribution"
    init_scatter_3d = go.Scatter(mode="markers")
    init_layout_3d = go.Layout(title="Samples from a 3-D Gaussian Distribution")
    init_fig_3d = go.Figure(data=[init_scatter_3d], layout=init_layout_3d)
    init_fig_3d.update_layout(
        margin=dict(l=4, r=3, t=80, b=10),
    )

    get_fig_3d, set_fig_3d = mo.state(init_fig_3d)
    get_clicks_3d, set_clicks_3d = mo.state(0)

    def add_sample_3d(_):
        fig_3d = get_fig_3d()
        x_3d = ["1", "2", "3"]
        y_3d = np.random.normal(size=3)
        new_scatter_3d = go.Scatter(
            x=x_3d, y=y_3d, mode="markers", name=f"Sample {get_clicks_3d()}"
        )
        fig_3d.add_trace(new_scatter_3d)
        set_fig_3d(fig_3d)
        set_clicks_3d(get_clicks_3d() + 1)

    def clear_data_3d(_):
        fig_3d = get_fig_3d()
        fig_3d.data = []
        set_fig_3d(fig_3d)
        set_clicks_3d(0)

    btn_new_sample_3d = mo.ui.button(
        value=0, on_click=add_sample_3d, label="New Sample", kind="success"
    )
    btn_clear_3d = mo.ui.button(
        value=get_clicks_3d(), on_click=clear_data_3d, label="Clear", kind="danger"
    )
    return btn_clear_3d, btn_new_sample_3d, get_fig_3d


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    Now let's take it to an extreme: a 50-D Gaussian. $\textbf{Y}_{50D} = [Y_1, Y_2, Y_3, \dots, Y_{50}]^T$, so every sample is a vector of 50 random values.
    """)
    return


@app.cell
def _(btn_clear_50d, btn_connect_50d, btn_new_sample_50d, get_fig_50d, mo):
    mo.vstack(
        [
            mo.ui.plotly(
                get_fig_50d(),
                config={"responsive": True, "displayModeBar": False, "staticPlot": True},
            ),
            mo.hstack([btn_new_sample_50d, btn_connect_50d, btn_clear_50d]),
        ]
    )
    return


@app.cell
def _(go, mo, np):
    # 50D Figure: "Samples from a 50-D Gaussian Distribution"
    init_scatter_50d = go.Scatter(mode="markers")
    init_layout_50d = go.Layout(title="Samples from a 50-D Gaussian Distribution")
    init_fig_50d = go.Figure(data=[init_scatter_50d], layout=init_layout_50d)
    init_fig_50d.update_layout(
        margin=dict(l=4, r=3, t=80, b=10),
    )

    get_fig_50d, set_fig_50d = mo.state(init_fig_50d)
    get_clicks_50d, set_clicks_50d = mo.state(0)

    def add_sample_50d(_):
        fig_50d = get_fig_50d()
        x_vals_50d = np.arange(50)
        y_vals_50d = np.random.normal(size=50)
        new_scatter_50d = go.Scatter(
            x=x_vals_50d, y=y_vals_50d, mode="markers", name=f"Sample {get_clicks_50d()}"
        )
        fig_50d.add_trace(new_scatter_50d)
        set_fig_50d(fig_50d)
        set_clicks_50d(get_clicks_50d() + 1)

    def connect_samples_50d(_):
        fig_50d = get_fig_50d()
        for trace in fig_50d.data:
            trace["mode"] = "lines+markers"
        set_fig_50d(fig_50d)

    def clear_data_50d(_):
        fig_50d = get_fig_50d()
        fig_50d.data = []
        set_fig_50d(fig_50d)
        set_clicks_50d(0)

    btn_new_sample_50d = mo.ui.button(
        value=0, on_click=add_sample_50d, label="New Sample", kind="success"
    )
    btn_connect_50d = mo.ui.button(
        label="Connect Points",
        on_click=connect_samples_50d,
    )
    btn_clear_50d = mo.ui.button(
        value=get_clicks_50d(), on_click=clear_data_50d, label="Clear", kind="danger"
    )
    return btn_clear_50d, btn_connect_50d, btn_new_sample_50d, get_fig_50d


@app.cell
def _(mo):
    mo.md(r"""
    Cool, so now we can visualize samples from a 50-D Gaussian in this kinda of weird way. How is this useful? And how does this relate to a Gaussian Process regression?

    You'll notice the above plot has a "Connect" button. If you click it, each variable in a given sample gets connected to the next.

    Do these connected samples remind you of anything? Maybe a certain class of elementary mathematical objects?

    If you thought "functions" then you are getting what I'm going for here. Each sample from the 50-D Gaussian is starting to look like some curve where, for any x-coordinate (which is just the index of the vector output of the multivariate gaussian) you can look up a y-value. So this kinda-sorta function can be defined as

    $$
    f(x) = Y_{x}
    $$

    given a multivariate Gaussian $Y = [Y_1, Y_2, Y_3, \dots, Y_{x}]^T \sim N(\boldsymbol{\mu}, \Sigma)$.

    But remember what each different colored curve is: it's a sample from a multivariate normal distribution. It's almost like the 50-D Gaussian specifies a _distribution over functions_...

    <img src="https://i.kym-cdn.com/entries/icons/original/000/007/630/conspiracykeanu.jpg" width="340" height="200" />

    _Almost_. The 50-D Gaussian really only specifies a distribution over 50 discrete values, so it's not quite a distribution over functions $f(x)$ that can take _any_ value of $x$. Hold that thought for now, we'll return to this later.

    But first you might have some questions. Remember, the above plot was made by taking a few samples from 50-D gaussian, $\textbf{Y}_{50D} \sim N(\boldsymbol{\mu}, \Sigma)$

    But I didn't tell you what $\boldsymbol{\mu}$ and $\Sigma$ were. Well, I actually used a mean vector of all zeros:

    $$
    \boldsymbol{\mu} =  \begin{bmatrix}
    0 \\
    0 \\
    \vdots \\
    0
    \end{bmatrix},
    $$

    and for the covariance matrix I simply used the Identity matrix.

    $$
    \Sigma = \begin{bmatrix}
    1 & 0 & \dots & 0 \\
    0 & 1 & \dots & 0 \\
    \vdots & \vdots & \ddots & \vdots \\
    0 & 0 & \dots & 1
    \end{bmatrix}.
    $$

    Since this covariance matrix is really big, let's visualize it with a heatmap:
    """)
    return


@app.cell
def _(PLOTLY_CONFIG, mo, np, plotly_heatmap):
    # @title
    mo.ui.plotly(plotly_heatmap(np.identity(50), title="Identity Matrix (50x50)"), config=PLOTLY_CONFIG)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    This means that each of the variables in our multivariate normal distribution are.....????
    """)
    return


@app.cell
def _(mo):
    # @title
    mo.Html(
        """
    <span class="hover-text">Hover or tap for answer</span>:

    <span class="hidden-text">INDEPENDENT!</span>

    <style>
      .hidden-text {
        display: none;
      }

      .hover-text:hover + .hidden-text {
        display: inline;
        font: 50px;
      }
    </style>
    """
    )
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    No variable has any covariance with any other, so you can think of this multivariate Gaussian as simply 50 separate Gaussians, each with mean = 0 and variance 1. This is why the curves we plotted above are so all over the place: each point is randomly bouncing up and down with no influence from its neighbors.

    What if we add some non-zero values to the covariance matrix that are off-diagonal?

    >Remember the diagonal elements of the matrix at row and column $i$ is $Cov(Y_i, Y_i) = Var(Y_i)$ while the off-diagonal elements at $i,j$ are $Cov(Y_i, Y_j)$.

    For example, check out the covariance matrix below:
    """)
    return


@app.cell
def _(PLOTLY_CONFIG, mo, np, pairwise_rbf, pd, plotly_heatmap, slider_l):
    _xa = np.arange(0, 50, 1).reshape(1, -1).T
    _xb = np.arange(0, 50, 1).reshape(1, -1).T
    C = pd.DataFrame(pairwise_rbf(_xa, _xb, slider_l.value))
    mo.ui.plotly(plotly_heatmap(C, title=f"ℓ={slider_l.value}"), config=PLOTLY_CONFIG)
    return (C,)


@app.cell
def _(mo):
    slider_l = mo.ui.slider(start=1, stop=30, value=5, label="Value of ℓ", debounce=True)
    slider_l
    return (slider_l,)


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    It looks very similar, but it's "fuzzier" around the diagonal. Think about what type of values you would expect from a Gaussian with this covariance matrix.

    (Try playing around with the mysterious "ℓ" slider, will explain later).

    It's saying that variables near each other are more correlated than variables far away. For example variable 1 is more correlated with variable 2 than it is with variable 50. Let visualize some samples from a 50-d Gaussian with this new covariance matrix. But before you hit the "sample" button, what do you think these new curves will look like?
    """)
    return


@app.cell
def _(btn_clear_fuzzy, btn_new_sample_fuzzy, get_fig_fuzzy, mo):
    # 4) Layout: Place the buttons side-by-side and display the figure
    mo.vstack(
        [
            mo.ui.plotly(
                get_fig_fuzzy(),
                config={"responsive": True, "displayModeBar": False, "staticPlot": True},
            ),
            mo.hstack([btn_new_sample_fuzzy, btn_clear_fuzzy]),
        ]
    )
    return


@app.cell
def _(go, mo, np, pairwise_rbf, slider_l):
    # 1) Create an initial figure
    init_scatter_fuzzy = go.Scatter(mode="markers")
    init_layout_fuzzy = go.Layout(title='Samples from a 50-D Gaussian <br>with "Fuzzy" Covariance')
    init_fig_fuzzy = go.Figure(data=[init_scatter_fuzzy], layout=init_layout_fuzzy)
    init_fig_fuzzy.update_layout(margin=dict(l=4, r=3, t=80, b=10), height=400)

    # 2) Store the figure in Marimo's state, plus a sample-count state
    get_fig_fuzzy, set_fig_fuzzy = mo.state(init_fig_fuzzy)
    get_clicks_fuzzy, set_clicks_fuzzy = mo.state(0)

    def add_sample_fuzzy(_):
        """Add a new random sample using a 'fuzzy' covariance matrix."""
        fig_fuzzy = get_fig_fuzzy()
        x = np.linspace(0, 50, 50)
        cov = pairwise_rbf(x.reshape(-1, 1), x.reshape(-1, 1), l=slider_l.value)
        y = np.random.multivariate_normal(mean=np.zeros(50), cov=cov, size=1)[0]
        sample_num = get_clicks_fuzzy()
        new_scatter_fuzzy = go.Scatter(
            x=x,
            y=y,
            mode="lines+markers",
            name=f"Sample {sample_num}",
        )
        fig_fuzzy.add_trace(new_scatter_fuzzy)
        set_fig_fuzzy(fig_fuzzy)
        set_clicks_fuzzy(sample_num + 1)

    def clear_data_fuzzy(_):
        """Clear all data from the fuzzy-covariance figure."""
        fig_fuzzy = get_fig_fuzzy()
        fig_fuzzy.data = []
        set_fig_fuzzy(fig_fuzzy)
        set_clicks_fuzzy(0)

    # 3) Create the UI buttons
    btn_new_sample_fuzzy = mo.ui.button(
        label="New Sample", on_click=add_sample_fuzzy, kind="success"
    )
    btn_clear_fuzzy = mo.ui.button(
        value=get_clicks_fuzzy(), on_click=clear_data_fuzzy, label="Clear", kind="danger"
    )
    return btn_clear_fuzzy, btn_new_sample_fuzzy, get_fig_fuzzy


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    Cool, they are now much smoother. This is because the variables near each other are more correlated, so nearby points are more likely to be similar. This smooths out the curves.

    Now we can see that by changing the covariance matrix, we can control the shape of the functions that our multivariate normal distribution produces.
    """)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ### Making these "functions" into Functions
    We've been throwing around the word "functions" a lot now, but we still never resolved the problem that these samples are really just 50-D vectors. Sure we can connect the points with little lines, but that's not the same as a function. How do we get a distribution over true functions?

    The answer lies in how we define the covariance and mean of our multivariate Gaussian. So far we've been manually inputting some mean vector and covariance matrix. Since these are objects with discrete, finite elements, we can't really think of the distributions they define as functions. But what if we could redefine these objects (the mean and covariance) as functions?

    Mathematically:

    $$
    \boldsymbol{\mu} = m(\textbf{x}) \\
    \Sigma = k(\textbf{x, x})
    $$

    Now for whatever $x$ we are interested in, we can sample from a multivariate Gaussian with mean $m(\textbf{x})$ and covariance $k(\textbf{x, x})$. This is one of those mathematical tricks that's so simple it's hard to understand, or maybe feels like cheating, so let's go through an example.

    Say we want to sample from a few specific real number $\textbf{x} = [-\pi, \pi, 2\pi]^T$ (some multiples of pi, as in 3.141...). First let's define a mean function $m(\textbf{x})$. We can use anything we like, so let's so something really simple: $m(\textbf{x}) = \textbf{x}$.

    For the covariance function $k(\textbf{x, x})$, we need a function of x that generates a symmetric matrix with a positive diagonal (otherwise it would not be a valid covariance). Again let's just do something really simple: $k(\textbf{x}, \textbf{x}) = \operatorname{diag}(\textbf{x} \odot \textbf{x} )$, where we take $\odot$ to mean the element-wise product of $\textbf{x}$ with $\textbf{x}$.

    > You maybe be wondering, "why define the covariance function as $k(\textbf{x, x})$ instead of simply $k(\textbf{x})$?". The reason is that covariance functions in general calculate a covariance between two vectors that are not necessarily the same. Here we are just calculating the covariance of $\textbf{x}$ with itself, but this will not always be the case...

    So if we put out test vector into these functions we get:

    $$
    \boldsymbol{\mu} = m(\textbf{x}) = \textbf{x} = [-\pi, \pi, 2\pi]^T\\
    $$

    $$
    \Sigma = k(\textbf{x}, \textbf{x}) = \operatorname{diag}(\textbf{x}\odot\textbf{x}) = \begin{bmatrix}
    (-\pi)^2 & 0 & 0 \\
    0 & (\pi)^2 & 0 \\
    0 & 0 & (2\pi)^2
    \end{bmatrix}
    $$

    Now we can sample from a multivariate Gaussian at these specific values of $x$:
    """)
    return


@app.cell
def _(PLOTLY_CONFIG, k, mo, np, pd, plotly_heatmap, x_specific):
    cov_df = pd.DataFrame(
        np.round(k(x_specific), 4), index=np.round(x_specific, 4), columns=np.round(x_specific, 4)
    )
    mo.ui.plotly(plotly_heatmap(cov_df, title="Covariance Function at Multiples of Pi"), config=PLOTLY_CONFIG)
    return


@app.cell
def _(btn_clear_real, btn_new_sample_real, get_fig_real, mo):
    mo.vstack(
        [
            mo.ui.plotly(
                get_fig_real(),
                config={"responsive": True, "displayModeBar": False, "staticPlot": True},
            ),
            mo.hstack([btn_new_sample_real, btn_clear_real]),
        ]
    )
    return


@app.cell
def _(go, mo, np):
    # Define the index points, mean function, and covariance function
    x_specific = np.array([-np.pi, np.pi, 2 * np.pi])
    m = lambda x: x
    k = lambda x: np.diag(x**2)

    # 1) Create a figure with an initial (empty) scatter trace
    init_scatter_real = go.Scatter(mode="markers")
    init_layout_real = go.Layout(title="Samples from a Multivariate Gaussian<br>at Multiples of Pi")
    init_fig_real = go.Figure(data=[init_scatter_real], layout=init_layout_real)
    init_fig_real.update_layout(margin=dict(l=4, r=3, t=80, b=10), height=400)
    # 2) Use Marimo state to keep track of the figure and click count
    get_fig_real, set_fig_real = mo.state(init_fig_real)
    get_clicks_real, set_clicks_real = mo.state(0)

    # 3) Define the callbacks
    def add_sample_real(_):
        fig_real = get_fig_real()
        # Build covariance and mean
        cov = k(x_specific)
        mean = m(x_specific)
        # Draw one sample from the multivariate normal
        y = np.random.multivariate_normal(mean=mean, cov=cov, size=1)[0]

        sample_num = get_clicks_real()
        new_scatter_real = go.Scatter(
            x=x_specific,
            y=y,
            mode="lines+markers",
            name=f"Sample {sample_num}",
        )
        fig_real.add_trace(new_scatter_real)

        set_fig_real(fig_real)
        set_clicks_real(sample_num + 1)

    def clear_data_real(_):
        fig_real = get_fig_real()
        fig_real.data = []
        set_fig_real(fig_real)
        set_clicks_real(0)

    # 4) Build UI: two buttons + the figure
    btn_new_sample_real = mo.ui.button(label="New Sample", on_click=add_sample_real, kind="success")
    btn_clear_real = mo.ui.button(
        value=get_clicks_real(), on_click=clear_data_real, label="Clear", kind="danger"
    )
    return btn_clear_real, btn_new_sample_real, get_fig_real, k, m, x_specific


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    But now that we've defined our mean and covariance functions, we can sample from a multivariate Gaussian at any value of $x$ we want. For example, let's sample at 50 evenly spaced real values of $x$ between -1 and 1. All we do is plug these values into our mean and covariance functions, and then sample from the resulting multivariate Gaussian.
    """)
    return


@app.cell
def _(PLOTLY_CONFIG, k, mo, np, pd, plotly_heatmap, x_real_big):
    _cov_df = pd.DataFrame(
        np.round(k(x_real_big), 4), index=np.round(x_real_big, 4), columns=np.round(x_real_big, 4)
    )
    mo.ui.plotly(plotly_heatmap(_cov_df, title="Covariance Function at 50<br>Evenly-Spaced Real Values"), config=PLOTLY_CONFIG)
    return


@app.cell
def _(btn_clear_50real, btn_new_sample_50real, get_fig_50real, mo):
    mo.vstack(
        [
            mo.ui.plotly(
                get_fig_50real(),
                config={"responsive": True, "displayModeBar": False, "staticPlot": True},
            ),
            mo.hstack([btn_new_sample_50real, btn_clear_50real]),
        ]
    )
    return


@app.cell
def _(go, k, m, mo, np):
    # We assume you've already defined:
    x_real_big = np.linspace(-1, 1, 50)
    # k = lambda x: np.diag(x**2)

    # 1) Create the initial figure
    init_scatter_50_real = go.Scatter(mode="markers")
    init_layout_50_real = go.Layout(
        title="Samples from a 50-D Multivariate Gaussian<br>at Real-Valued Indices"
    )
    init_fig_50_real = go.Figure(data=[init_scatter_50_real], layout=init_layout_50_real)
    init_fig_50_real.update_layout(margin=dict(l=4, r=3, t=80, b=10), height=400)

    # 2) Store the figure and a sample counter in Marimo's state
    get_fig_50real, set_fig_50real = mo.state(init_fig_50_real)
    get_clicks_50real, set_clicks_50real = mo.state(0)

    def add_sample_50real(_):
        """Draw one random sample from a 50-D Gaussian (diag covariance = x^2)."""
        fig_50r = get_fig_50real()
        sample_num = get_clicks_50real()

        # Build covariance and mean from the user-defined functions
        cov_50 = k(x_real_big)
        mean_50 = m(x_real_big)
        # Draw a single 50-D sample
        y_samp = np.random.multivariate_normal(mean=mean_50, cov=cov_50, size=1)[0]

        new_scatter_50r = go.Scatter(
            x=x_real_big,
            y=y_samp,
            mode="lines+markers",
            name=f"Sample {sample_num}",
        )
        fig_50r.add_trace(new_scatter_50r)

        set_fig_50real(fig_50r)
        set_clicks_50real(sample_num + 1)

    def clear_data_50real(_):
        """Remove all existing traces."""
        fig_50r = get_fig_50real()
        fig_50r.data = []
        set_fig_50real(fig_50r)
        set_clicks_50real(0)

    # 3) Create the UI: Two buttons + the figure
    btn_new_sample_50real = mo.ui.button(
        label="New Sample", on_click=add_sample_50real, kind="success"
    )

    btn_clear_50real = mo.ui.button(label="Clear", on_click=clear_data_50real, kind="danger")
    return btn_clear_50real, btn_new_sample_50real, get_fig_50real, x_real_big


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    Now we've truly got a distribution over functions.

    If we want the distribution at _any_ value $x$, we can just plug it in to the mean and covariance functions and voila! We just need to define a mean and valid covariance function that we like, and we can sample from a multivariate Gaussian at any value of $x$ we want.

    By the way, "covariance functions" are usually referred to by a fancy name: **kernel functions**. Remember this plot of a covariance matrix from earlier?
    """)
    return


@app.cell
def _(C, PLOTLY_CONFIG, mo, plotly_heatmap, slider_l):
    mo.ui.plotly(plotly_heatmap(C, title=f"ℓ={slider_l.value}"), config=PLOTLY_CONFIG)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    This covariance we actually generated by using a specific kernel function called the squared exponential kernel, a.k.a. the Gaussian kernel a.k.a the radial basis function (RBF) kernel. I'll refer to it as the RBF kernel for this post.

    It's defined as:

    $$
    k(\textbf{x}) = \exp\left(-\frac{1}{2ℓ^2} ||\textbf{x} - \textbf{x}||^2\right)
    $$

    where $||\textbf{x} - \textbf{x}||^2$ is the element-wise squared difference matrix between each element of $x$ with each other element, and $ℓ$ is an adjustable parameter.

    No need to worry about the math here too closely. The important thing to note is that the RBF kernel is a function of $\textbf{x}$ that generates a positive semidefinite matrix. It's a covariance function, a.k.a. kernel, and it happens to be one of the most useful kernels in the real-world.
    """)
    return


@app.cell
def _(mo, np, sp):
    # The RBF kernel, implemented in python with numpy
    def pairwise_rbf(xa, xb, l=5.0):
        sq_norm = (-0.5 / l**2) * sp.spatial.distance.cdist(xa, xb, "sqeuclidean")
        return np.exp(sq_norm)

    mo.show_code()
    return (pairwise_rbf,)


@app.cell
def _(mo):
    code = """
# Try editing these to be whatever you want.
# Note you can add as may points as you like!
points = [1.549, 2, 3, 4, 5, 6, 10]
# You can change the value of l to see how it changes the covariance matrix
l = 1

#=========================================
# The rest of this code feeds these points into the pairwise_rbf function
# and plots the resulting covariance matrix
x_test = np.array(points).reshape(-1, 1)
rbf_output = pairwise_rbf(x_test, x_test, l=l)
plot = plotly_heatmap(rbf_output, annot=True, xticklabels=points, yticklabels=points)
"""
    code_editor = mo.ui.code_editor(value=code)
    code_editor
    return (code_editor,)


@app.cell
def _(PLOTLY_CONFIG, code_editor, mo, np, pairwise_rbf, plotly_heatmap):
    _locals = {"np": np, "pairwise_rbf": pairwise_rbf, "plotly_heatmap": plotly_heatmap}
    exec(code_editor.value, _locals)
    mo.ui.plotly(_locals.get("plot"), config=PLOTLY_CONFIG)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    Using this kernel function, lets sample from a multivariate Gaussian at 50 evenly spaced real values of $x$ between -1 and 1. But this time you can adjust the slider to change the value of the kernel's $l$ parameter and see how it changes the shape of the covariance matrix and the resulting distribution over functions.
    """)
    return


@app.cell
def _(
    btn_clear_double,
    btn_new_sample_double,
    get_fig_cov,
    get_fig_samples,
    mo,
    slider_ld,
):
    mo.vstack(
        [
            mo.ui.plotly(
                get_fig_samples(),
                config={"responsive": True, "displayModeBar": False, "staticPlot": True},
            ),
            mo.hstack([btn_new_sample_double, btn_clear_double]),
            slider_ld,
            mo.ui.plotly(
                get_fig_cov(),
                config={"responsive": True, "displayModeBar": False, "staticPlot": True},
            ),
        ]
    )
    return


@app.cell
def _(go, mo, np, pairwise_rbf):
    #################################################################
    # 2) Prepare initial data
    #################################################################

    xa = np.linspace(-1, 1, 50).reshape(-1, 1)
    init_cov = pairwise_rbf(xa, xa, l=0.5)  # initial length scale

    #################################################################
    # 3) Build the two separate Plotly figures
    #################################################################

    # -- Figure A: "Function Samples" --
    fig_samples = go.Figure()
    # Start with an empty scatter for function samples
    scatter_init = go.Scatter(mode="lines", x=[], y=[], name="Samples")
    fig_samples.add_trace(scatter_init)
    fig_samples.update_yaxes(range=[-5, 5], fixedrange=True)
    fig_samples.update_layout(
        title="Function Samples", margin=dict(l=20, r=20, t=40, b=20), height=350
    )

    # -- Figure B: "Covariance Matrix" --
    fig_cov = go.Figure()
    # Create a 50×50 heatmap; rotate it so indexing matches your original code
    z = np.rot90(init_cov)
    xa_rounded = xa.flatten()  # round for better x-axis labels
    heatmap_init = go.Heatmap(
        z=z,
        x=xa_rounded,
        y=xa_rounded,
        showscale=False,
    )
    fig_cov.add_trace(heatmap_init)
    # Make it "square" in data coordinates
    # fig_cov.update_xaxes(range=[0, 49])
    # fig_cov.update_yaxes(range=[0, 49], scaleanchor="x", scaleratio=1)  # tie y-axis scale to x-axis
    fig_cov.update_layout(
        title="Covariance Matrix",
        width=350,
        height=350,
        margin=dict(l=20, r=20, t=40, b=20),
    )

    #################################################################
    # 4) Store the figures and relevant parameters in Marimo state
    #################################################################

    get_fig_samples, set_fig_samples = mo.state(fig_samples)
    get_fig_cov, set_fig_cov = mo.state(fig_cov)

    get_l_param, set_l_param = mo.state(0.5)
    get_cov, set_cov = mo.state(init_cov)

    #################################################################
    # 5) Define the callback functions
    #################################################################

    def on_slider_change(new_l):
        """
        1) Update the stored length scale
        2) Recompute the covariance
        3) Update the heatmap in fig_cov
        """
        set_l_param(new_l)
        new_cov = pairwise_rbf(xa, xa, l=new_l)
        set_cov(new_cov)

        fig_c = get_fig_cov()
        fig_c.data[0].z = np.rot90(new_cov)  # data[0] is the heatmap
        set_fig_cov(fig_c)

    def add_new_sample(_):
        """
        Generate a random function sample from the current covariance
        and add it to fig_samples.
        """
        current_cov = get_cov()

        # Draw a random sample from the multivariate normal
        y_samp = np.random.multivariate_normal(mean=np.zeros(len(xa)), cov=current_cov, size=1)[0]

        fig_s = get_fig_samples()
        new_trace = go.Scatter(
            x=xa.ravel(),
            y=y_samp,
            mode="lines",
            name=f"ℓ={get_l_param():.2f}",
        )
        fig_s.add_trace(new_trace)
        set_fig_samples(fig_s)

    def clear_figure(_):
        """
        Reset the samples figure so it has only one empty scatter trace.
        Also reset the sample counter to 0.
        """
        fig_s = get_fig_samples()
        fig_s.data = fig_s.data[:1]
        set_fig_samples(fig_s)

    #################################################################
    # 6) Build the UI (slider + two buttons + display figures)
    #################################################################

    slider_ld = mo.ui.slider(
        value=get_l_param(),
        start=0.01,
        stop=2.0,
        step=0.01,
        on_change=on_slider_change,
        label="RBF Kernel Parameter (ℓ)",
    )

    btn_new_sample_double = mo.ui.button(
        label="New Sample", on_click=add_new_sample, kind="success"
    )

    btn_clear_double = mo.ui.button(label="Clear", on_click=clear_figure, kind="danger")
    return (
        btn_clear_double,
        btn_new_sample_double,
        get_fig_cov,
        get_fig_samples,
        slider_ld,
    )


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## Conditioning on Data

    Wow, we've come a long way. Let's regroup here and remember our original definition of a Gaussian Process Regression.

    **GP Regression: <font color="#32a852">A Multivariate Gaussian Distribution over functions</font>, conditioned on some training data.**

    > In fact this highlighted part above is the definition of a Gaussian Process. But we want "Gaussian Process Regression". (People sometimes use the two to mean the same thing, but technically GP is the distribution and GPR is the regression problem.)

    We're more than half-way done! But we still need to condition it on some training data. Right now we're just sampling these pretty functions, but they are completely random.

    Conditioning means we want the probability of some outcome given some data. Mathematically we write this as:

    $$
    p(y | x)
    $$

    that is, the probability of some outcome $y$ given some other data $x$.

    Let's take a simple toy problem as a concrete example:

    Say we are trying to predict the cost of a house along a particular road. At one end of the road, there is a nuclear power plant (yikes). We have some data on the cost of some of the houses on this road, but we want to predict the cost of a house at any location. Let's look at the data first:
    """)
    return


@app.cell
def _(PLOTLY_CONFIG, go, mo, np, pd):
    # @title
    X = np.array(
        [
            [9.34825241e00],
            [9.67438030e00],
            [1.17250505e01],
            [5.99427279e00],
            [1.07375146e01],
            [3.87950162e00],
            [2.71045131e00],
            [7.35740185e00],
            [9.13638194e00],
            [1.05863164e01],
            [7.42074188e00],
            [1.20328572e01],
            [5.15531137e00],
            [3.24806136e-01],
            [1.32962952e-03],
        ]
    )
    y = np.array(
        [
            [295011.54177245],
            [291803.4301587],
            [302340.03191297],
            [254244.52812629],
            [288037.40660445],
            [225340.17067212],
            [235462.67258466],
            [291158.36183822],
            [297052.11645609],
            [287514.83630223],
            [292359.62730391],
            [310157.34073017],
            [233483.05286424],
            [209630.56264745],
            [200039.88887763],
        ]
    )
    DOMAIN = (0, 4 * np.pi)
    X_axis = np.linspace(DOMAIN[0], DOMAIN[1], 50).reshape(1, -1).T
    y_true = (0.1 * np.sin(X_axis) + 1) * 200000 + X_axis * 10000
    X_test = np.linspace(DOMAIN[0], DOMAIN[1], 50).reshape(1, -1).T
    df = pd.DataFrame(y.flatten(), index=X.flatten(), columns=["Cost of a house"]).sort_index()
    df.index.name = "Distance from the Nuclear Power Plant (miles)"
    # Plot with Plotly instead of pandas/matplotlib
    fig_housing = go.Figure(data=go.Scatter(
        x=df.index, y=df["Cost of a house"], mode='markers', marker=dict(color='red')
    ))
    fig_housing.update_layout(
        xaxis_title="Distance from the Nuclear Power Plant (miles)",
        yaxis_title="Cost of a house",
        margin=dict(l=60, r=20, t=40, b=60),
    )
    mo.ui.plotly(fig_housing, config=PLOTLY_CONFIG)
    return X, X_axis, X_test, y, y_true


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    Right away we see a couple things. Housing costs are not just linearly increasing as we get further away from the plant; there seem to be a few dips. Maybe there is a prison 5 miles away from the plant; who knows. Regardless, we probably want some non-linear model for this data.

    The main question at hand is given this known cost data, what is the expected cost of a house at another location $x$?

    To state this mathematically, we want some function structured as follows:

    $$
    p(\textbf{c} | \textbf{x})
    $$

    That is, we want the probability distribution of cost of a house $c$, given its distance $x$ from the nuclear plant. Since we've been thinking about multivariate Gaussian, let's make an assumption that the distribution above follows a multivariate Gaussian.

    $$
    p(\textbf{c} | \textbf{x}) \sim N(m(\textbf{x}), k(\textbf{x}, \textbf{x}))
    $$

    Where $k(\textbf{x}, \textbf{x})$ is the covariance function, and $m(\textbf{x})$ is the mean function. For now we'll just assume that the mean function is zero, and for the covariance function we'll use the RBF kernel.

    Why these? Remember the RBF function's effect above: it sort of "smooths" out the data. This makes sense to model housing prices, because it's reasonable to expect that houses near each other will have similar prices.

    > But why is the mean function zero? A: trust me bro. It just works out in practice that mean = 0 is usually good enough to model the data. For example sklearn's GP implementation doesn't even let you specify a mean function. For more on this see [Section 2.7 here](http://gaussianprocess.org/gpml/chapters/RW2.pdf).

    We really need the following if we want to condition on the known data:

    $$
    p(\textbf{c} | \textbf{x}, \textbf{c}_{\text{known}}, \textbf{x}_{\text{known}})
    $$

    Putting this into words, we want the probability distribution of prices of a house, given its location _and_ given the prices of houses at some other locations.

    Let's assume that the known data also came from the same multivariate Gaussian distribution as the unknown. So we can write:


    $$
    p(\textbf{c}_{\text{known}}| \textbf{x}_{\text{known}}) \sim N(0, k(\textbf{x}_{\text{known}}, \textbf{x}_{\text{known}}))
    $$

    And for the unknown data, remember we had:

    $$
    p(\textbf{c} | \textbf{x}) \sim N(0, k(\textbf{x}, \textbf{x}))
    $$

    Notice that we've assumed both the known data and the unknown data come from multivariate Gaussians. What if we just combined them into one big multivariate gaussian? We could basically just stack the distributions on top of each other to form a big "mother" Gaussian.

    $$
    p(\begin{bmatrix} \textbf{c} \\ \textbf{c}_{\text{known}} \end{bmatrix} | \begin{bmatrix} \textbf{x} \\ \textbf{x}_{\text{known}} \end{bmatrix}) \sim N\left(\begin{bmatrix}0 \\ 0\end{bmatrix}, \begin{bmatrix}k(\textbf{x}, \textbf{x}) & k(\textbf{x}, \textbf{x}_{\text{known}}) \\ k(\textbf{x}_{\text{known}}, \textbf{x}) & k(\textbf{x}_{\text{known} }, \textbf{x}_{\text{known}})\end{bmatrix}\right)
    $$

    The one wrinkle here is the covariance function. For the off-diagonal elements, we need to use the covariance function between the unknown data and the known data. So _now_ we see why the kernel function is written as $k(\textbf{x}, \textbf{x})$; in this case we need to compute the covariance between two different vectors of data to fill in the off-diagonal blocks of the covariance matrix above.

    Can we massage the beast above into a probability distribution conditioned on the known data? Like so:

    $p(\textbf{c} | \textbf{x}, \textbf{c}_{\text{known}}, \textbf{x}_{\text{known}}) \sim ???$

    The answer is yes. It's the following:

    $$
    p(\textbf{c} | \textbf{x}, \textbf{c}_{\text{known}}, \textbf{x}_{\text{known}}) \sim N\left(m(\textbf{x}) + k(\textbf{x}, \textbf{x}_{\text{known}})k(\textbf{x}_{\text{known}})^{-1}(\textbf{c}_{\text{known}} - m(\textbf{x}_{\text{known}})), k(\textbf{x}) - k(\textbf{x}, \textbf{x}_{\text{known}})k(\textbf{x}_{\text{known}})^{-1}k(\textbf{x}_{\text{known}}, \textbf{x})\right)
    $$

    > Please don't get mad at me for just giving you the answer. It's a kind of complicated derivation, and I don't want us to get bogged down. If you want to go through it, see this section of [Gaussian Processes for Machine Learning](http://gaussianprocess.org/gpml/chapters/RW.pdf#page=218&zoom=50,240,358).
    >
    > For now, just accept that there's a nice closed form solution to this problem.

    Wait, uh, so we're done?

    **GP Regression: <font color="#32a852">A Multivariate Gaussian Distribution over functions, conditioned on some training data.</font>**

    We're done! We've got a nice closed form distribution over functions conditioned on some data.
    """)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    # Actually Fitting a Regression Model

    Using our conditional distribution above, we can plug in our known house costs to create a conditional distribution of functions. Then we can sample from this distribution at, say, 50 evenly spaced distance from 0 to 12 miles away from the nuclear plant.

    We have 15 known cost data points. This means that $\textbf{c}_{\text{known}}$ and $\textbf{x}_{\text{known}}$ is are vectors of length 15. We want to predicted prices at 50 evenly spaced points, so $\textbf{x}$ and $\textbf{c}$ are vectors of length 50.

    Plugging this into the conditional distribution above, we can now sample from the conditional distribution of functions:

    > Note: we're using the RBF kernel here with parameter $ℓ$ set to 1.0.
    """)
    return


@app.cell
def _(pairwise_rbf, sp):
    def gp_posterior(y_train, X_train, X_test, l=1.0):
        """
        Given known data (y_train, X_train), and some unknown input values(X_test)
        calculate the conditional mean vector (mu_2__1) and conditional covariance matrix
        (sigma_2__1) of a Gaussian process with RBF kernel.
        """
        sigma_11 = pairwise_rbf(X_train, X_train, l=l)
        sigma_21 = pairwise_rbf(X_train, X_test, l=l).T
        sigma_22 = pairwise_rbf(X_test, X_test, l=l)
        sigma_12 = sigma_21.T
        mu_2__1 = (sigma_21 @ sp.linalg.inv(sigma_11) @ y_train).flatten()
        sigma_2__1 = sigma_22 - sigma_21 @ sp.linalg.inv(sigma_11) @ sigma_12
        return (mu_2__1, sigma_2__1)

    return (gp_posterior,)


@app.cell
def _(btn_clear_housing, btn_new_sample_housing, get_fig_housing, mo):
    get_fig_housing()

    mo.vstack(
        [
            mo.ui.plotly(
                get_fig_housing(),
                config={"responsive": True, "displayModeBar": False, "staticPlot": True},
            ),
            mo.hstack([btn_new_sample_housing, btn_clear_housing]),
        ]
    )
    return


@app.cell
def _(X, X_test, calculate_figure_height, go, gp_posterior, mo, np, y):
    # We'll assume y, X, X_test, and gp_posterior(...) are already defined above.
    # y is the original housing data, X the known inputs, X_test the test inputs.

    # Normalize y
    _y_norm = (y - y.mean()) / y.std()
    mu, sigma = gp_posterior(_y_norm, X, X_test, l=1)  # gp_posterior returns mean & covariance

    # 1) Create initial figure with known housing data
    scatter_known = go.Scatter(
        x=X.T[0], y=y.T[0], mode="markers", marker=dict(color="red", size=16), name="Known Data"
    )
    layout_housing = go.Layout(
        title="Samples from a Gaussian Process<br>Conditioned on Known Housing Data",
        xaxis_title="Distance from the Nuclear Power Plant (miles)",
        yaxis_title="Cost of a house ($)",
    )
    init_fig_housing = go.Figure(data=[scatter_known], layout=layout_housing)
    init_fig_housing.update_layout(
        margin=dict(l=4, r=3, t=80, b=10),
    )

    # Initial height calculation
    initial_height2 = calculate_figure_height(4)  # Start with 4 traces

    # Update layout with side-by-side grouped legend
    init_fig_housing.update_layout(
        height=initial_height2,
        legend=dict(
            entrywidth=0.29,
            entrywidthmode="fraction",
            orientation="h",
            yanchor="bottom",
            y=-0.2,
            xanchor="center",
            x=0.5,
            bgcolor="white",
            bordercolor="LightGrey",
            borderwidth=0,
            itemsizing="constant",
            itemwidth=30,
            groupclick="toggleitem",
            valign="middle",
            xref="container",
            yref="container",
            traceorder="grouped",
            font=dict(size=10),
        ),
        margin=dict(l=4, r=3, t=80, b=80),
    )

    # 2) Wrap the figure and a sample counter in Marimo's state
    get_fig_housing, set_fig_housing = mo.state(init_fig_housing)
    get_clicks_housing, set_clicks_housing = mo.state(0)

    def add_sample_housing(_):
        """
        Draw a random sample from the GP posterior (mu, sigma),
        un-normalize it, and add it to the figure as a new trace.
        """
        fig_housing = get_fig_housing()
        current_clicks = get_clicks_housing()

        # Draw a single sample from the posterior (50D)
        # Then "un-normalize" it back to actual scale
        yp = np.random.multivariate_normal(mean=mu, cov=sigma, size=1)[0] * y.std() + y.mean()
        new_scatter = go.Scatter(
            x=X_test.T[0], y=yp, mode="lines+markers", name=f"Sample {current_clicks}"
        )
        fig_housing.add_trace(new_scatter)
        new_height = calculate_figure_height(len(fig_housing.data))
        fig_housing.update_layout(height=new_height)

        set_fig_housing(fig_housing)

        set_clicks_housing(current_clicks + 1)

    def clear_data_housing(_):
        """
        Reset the figure to only contain the original known data trace.
        Reset the sample counter to zero.
        """
        fig_housing = get_fig_housing()
        # Keep only the first trace (the known data)
        fig_housing.data = fig_housing.data[:1]
        set_fig_housing(fig_housing)
        set_clicks_housing(0)

    # 3) Create the UI: two buttons + the figure
    btn_new_sample_housing = mo.ui.button(
        label="New Sample", on_click=add_sample_housing, kind="success"
    )
    btn_clear_housing = mo.ui.button(label="Clear", on_click=clear_data_housing, kind="danger")

    # 4) Display everything
    return (
        btn_clear_housing,
        btn_new_sample_housing,
        get_fig_housing,
        mu,
        sigma,
    )


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    Yeah baby. Now _this_ looks like a Gaussian process regression. Clearly the samples from the distribution are conditioned on known data, because all the functions we sample pass through the known data points. But in between the known data points the functions are free to somewhat randomly vary, giving us an idea of the uncertainty. How smoothly the functions vary is determined by the covariance function, which in this case is the RBF kernel.

    In the plot below, I reveal the true underlying function I used to generate this "housing data" (pink). What if we take 500 samples from this posterior distribution?
    """)
    return


@app.cell
def _(PLOTLY_CONFIG, get_many_fig, many, mo):
    mo.vstack([mo.ui.plotly(get_many_fig(), config=PLOTLY_CONFIG), many])
    return


@app.cell
def _(X, X_axis, X_test, go, gp_posterior, mo, np, y, y_true):
    # Create initial figure with baseline (true function + known data)
    def create_baseline_fig():
        fig = go.Figure()
        # True underlying function (pink)
        sorted_idx = np.argsort(X_axis.flatten())
        fig.add_trace(go.Scatter(
            x=X_axis.flatten()[sorted_idx],
            y=y_true.flatten()[sorted_idx],
            mode='lines',
            line=dict(color='#ff54e0', width=2),
            name='Underlying Function'
        ))
        # Known data points (red)
        fig.add_trace(go.Scatter(
            x=X.flatten(),
            y=y.flatten(),
            mode='markers',
            marker=dict(color='red', size=8),
            name='Known Data'
        ))
        fig.update_layout(
            xaxis_title="Distance from Nuclear Power Plant (miles)",
            yaxis_title="Price",
            margin=dict(l=60, r=20, t=40, b=60),
            height=400,
        )
        return fig

    # State for the figure
    get_many_fig, set_many_fig = mo.state(create_baseline_fig())

    def add_posterior_samples(_):
        """Add 500 posterior samples to the plot."""
        fig = get_many_fig()
        # Normalize y
        _y_norm = (y - y.mean()) / y.std()
        mu_1, sigma_1 = gp_posterior(_y_norm, X, X_test, l=1)
        # Draw 500 samples
        y_hat = np.random.multivariate_normal(mu_1, sigma_1, size=500) * y.std() + y.mean()
        sorted_idx = np.argsort(X_test.flatten())
        x_sorted = X_test.flatten()[sorted_idx]
        # Add each sample as a trace
        for i in range(y_hat.shape[0]):
            fig.add_trace(go.Scatter(
                x=x_sorted,
                y=y_hat[i][sorted_idx],
                mode='lines',
                line=dict(color='blue', width=1),
                opacity=0.02,
                showlegend=False,
            ))
        set_many_fig(fig)

    many = mo.ui.button(
        on_click=add_posterior_samples,
        label="Sample 500 Functions from Posterior",
        kind="success",
    )
    return (get_many_fig, many)


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    Remember what there blue lines are: they are samples from a multivariate gaussian conditioned on the known data points, and sampled at 500 evenly spaced points between 0 and 12. We used the complicated formula above to find the conditional mean vector and conditional covariance matrix, and then sampled from a distribution using that mean and covariance.

    Below are some heatmaps of the _conditional_ covariance matrix and _conditional_ mean vector (conditioned on the known housing data) that specify the predictive multivariate gaussian distribution.

    Think for a moment about why this conditional mean and covariance makes sense.
    """)
    return


@app.cell
def _(PLOTLY_CONFIG, X_test, mo, pd, plotly_heatmap, sigma):
    # @title
    ix = X_test.flatten().round(2)
    cov_fig = plotly_heatmap(pd.DataFrame(sigma, index=ix, columns=ix), title="Conditional Covariance Matrix")
    mo.ui.plotly(cov_fig, config=PLOTLY_CONFIG)
    return (ix,)


@app.cell
def _(PLOTLY_CONFIG, ix, mo, mu, pd, plotly_heatmap, y):
    mean_fig = plotly_heatmap(
        pd.DataFrame((mu * y.std() + y.mean()).reshape(-1, 1), index=ix),
        title="Conditional Mean Vector"
    )
    mo.ui.plotly(mean_fig, config=PLOTLY_CONFIG)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## Outro

    You should now have the core ideas of Gaussian processes regression. If you still have some questions, like:

    - "Do you really have to sample 100s of functions to get the confidence intervals?"
        - (You should now be able to figure out the answer to this.)
    - "How do we choose a kernel function?"
    - "How do we choose the best parameters for the kernel function?"
    - "What if the training data is intrinsically noisy (the price of houses has some variance at a given location)
      "
    - "What if there are many features in my training data? E.g. Square footage of houses."
    - "But I heard GPs are expensive to train?"

    ...then you should check out the resources below, which should be easier to understand now that you have the basics.
    """)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## References

    ### Tutorials and Guides
    - **[Gaussian Process Tutorial](https://peterroelants.github.io/posts/gaussian-process-tutorial/)** - Really awesome set of blog posts that teaches GPs using Python. I basically took this post and made it more verbose. The other posts in the series go into more detail about the process of fitting a GP and optimizing the kernel and hyperparameters.

    - **[Visual Exploration of Gaussian Processes](https://distill.pub/2019/visual-exploration-gaussian-processes/)** - More detailed, with beautiful interactive visualizations. Explores other non-RBF kernel functions more.

    - **[Fitting Gaussian Process Models in Python](https://www.dominodatalab.com/blog/fitting-gaussian-process-models-python)** - Practical guide focused on implementing GPs using scikit-learn and other Python libraries.

    ### Advanced Reading
    - **[Gaussian Processes for Machine Learning](http://gaussianprocess.org/gpml/chapters/)** - _The book_ on GPs, with all the detail you'll ever need.
    """)
    return


@app.cell
def _():
    import altair as alt

    return (alt,)


@app.cell
def _():
    return


if __name__ == "__main__":
    app.run()
