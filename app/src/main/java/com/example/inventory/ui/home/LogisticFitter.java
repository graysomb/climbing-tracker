package com.example.inventory.ui.home;

import org.apache.commons.math3.analysis.ParametricUnivariateFunction;
import org.apache.commons.math3.fitting.CurveFitter;
import org.apache.commons.math3.fitting.WeightedObservedPoint;

public class LogisticFitter {

    public static double[] fitLogistic(double[] xValues, double[] yValues) {
        // Ensure xValues and yValues arrays have the same length
        if (xValues.length != yValues.length) {
            throw new IllegalArgumentException("xValues and yValues must have the same length.");
        }

        // Create a CurveFitter with a Levenberg-Marquardt optimizer
        CurveFitter<ParametricUnivariateFunction> fitter = new CurveFitter<>(
                new org.apache.commons.math3.optim.nonlinear.vector.jacobian.LevenbergMarquardtOptimizer()
        );

        // Add observed points from xValues and yValues arrays
        for (int i = 0; i < xValues.length; i++) {
            fitter.addObservedPoint(new WeightedObservedPoint(1.0, xValues[i], yValues[i]));
        }

        // Define the logistic function
        ParametricUnivariateFunction logistic = new ParametricUnivariateFunction() {
            @Override
            public double value(double x, double... parameters) {
                double L = parameters[0]; // Maximum value (asymptote)
                double k = parameters[1]; // Growth rate
                double x0 = parameters[2]; // Midpoint
                return L / (1 + Math.exp(-k * (x - x0)));
            }

            @Override
            public double[] gradient(double x, double... parameters) {
                double L = parameters[0];
                double k = parameters[1];
                double x0 = parameters[2];

                double expTerm = Math.exp(-k * (x - x0));
                double denom = (1 + expTerm);
                double denomSq = denom * denom;

                double dL = 1 / denom;
                double dk = (L * (x - x0) * expTerm) / denomSq;
                double dx0 = -(L * k * expTerm) / denomSq;

                return new double[]{dL, dk, dx0};
            }
        };

        // Initial guess for the parameters: [L, k, x0]
        double[] initialGuess = {1.0, -0.1, 6.0};

        // Fit the logistic function
        return fitter.fit(logistic, initialGuess);
    }

    public static void main(String[] args) {
        // Example x and y values
        double[] xValues = {1.0, 2.0, 3.0};
        double[] yValues = {0.5, 0.8, 0.9};

        // Fit logistic model
        double[] bestFit = fitLogistic(xValues, yValues);

        // Output the fitted parameters
        System.out.println("Fitted parameters:");
        for (double param : bestFit) {
            System.out.println(param);
        }
    }
}
