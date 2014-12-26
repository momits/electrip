#!/usr/bin/env python
# -*- coding: UTF 8 -*-


class LinearSegmentFunction:
    """
    Function consisting of linear segments which build a
    continuous line connecting certain control points.
    The function increases monotonically.
    """
    def load(self, control_points):
        """
        Loads the function from the control points, building
        the linear function segments between the control-points.
        *control_points* are a list of ``(x, y)``-point-tuples
        defining the control-points of the function.
        """
        self.control_points = [control_points[0], control_points[-1]]
        self.func_segments = [self.calc_func_segment(self.control_points[0],
                                                     self.control_points[-1])]
        for point in control_points[1:len(control_points) - 1]:
            self.add_control_point(*point)
    
    def add_control_point(self, x, y):
        """
        Adds a control point at ``(x, y)``, updating the function.
        If the resulting function after inserting ``(x, y)`` would
        not be monotonically increasing, nothing will happen. If *x*
        lies outside the existing segments, behaviour is undefined.
        """
        # no good to have two points at one spot:
        if not (x, y) in self.control_points:
            nr = self.get_segment_nr_from_x(x)
            if nr:
                self.control_points.insert(nr + 1,
                                           (x,
                                            max(self.control_points[nr][1] ,
                                            min(y, self.control_points[nr + 1][1]))))
                self.func_segments[nr] = self.calc_func_segment(self.control_points[nr],
                                                                self.control_points[nr + 1])
                self.func_segments.insert(nr + 1,
                                          self.calc_func_segment(self.control_points[nr + 1],
                                                                 self.control_points[nr + 2]))
                
    def remove_control_point(self, nr):
        """
        Removes the *nr*-th control point from the function.
        Attempting to delete the first or last control point
        will result in nothing happening, because they are
        necessary for the function to exist.
        """
        if nr != 0 and nr != len(self.control_points) - 1:
            self.control_points.pop(nr)
            del self.func_segments[nr - 1: nr + 1]
            self.func_segments.insert(nr - 1,
                                      self.calc_func_segment(self.control_points[nr - 1],
                                                             self.control_points[nr]))
        
    def move_control_point(self, nr, x, y):
        """
        Moves the *nr*-th control point to the point ``(x, y)``.
        If ``x > x of the next point``, nothing will happen, to ensure
        a monotonic increase (Same for ``y > y of next point``).
        """
        if nr == len(self.control_points) - 1:
            point_left = self.control_points[nr - 1]
            self.control_points[nr] = (self.control_points[nr][0],
                                       max(y, point_left[1]))
            self.func_segments[nr - 1] = self.calc_func_segment(point_left,
                                                                self.control_points[nr])
        elif nr == 0:
            point_right = self.control_points[nr + 1]
            self.control_points[nr] = (self.control_points[nr][0],
                                       min(y, point_right[1]))
            self.func_segments[nr] = self.calc_func_segment(self.control_points[nr],
                                                            point_right)
            
        else:
            point_left = self.control_points[nr - 1]
            point_right = self.control_points[nr + 1]
            
            if point_left[0] < x < point_right[0]:
                self.control_points[nr] = (x,
                                           min(point_right[1],
                                           max(y, point_left[1])))
                self.func_segments[nr] = self.calc_func_segment(self.control_points[nr],
                                                                point_right)
                self.func_segments[nr - 1] = self.calc_func_segment(point_left,
                                                                    self.control_points[nr])
        return self.control_points[nr]
                        
    @staticmethod
    def calc_func_segment(point1, point2):
        """
        Solves the equation y=a*x+b using the
        two points ``(x1, y1)`` and ``(x2, y2)``.
        Returns ``(a, b)``.
        """
        x1, y1 = point1
        x2, y2 = point2
        a = (y2 - y1) / (x2 - x1)
        b = y2 - x2 * a
        return a, b
            
    def get_y(self, x):
        """
        Returns the functions y-value at *x*.
        """
        if x == 0:
            return 0
        else:
            seg_nr = self.get_segment_nr_from_x(x)
            if seg_nr is not None:
                a, b = self.func_segments[seg_nr]
                y = a * x + b
                return y
    
    def get_x(self, y):
        """
        Returns the functions x-value matching *y*.
        (Possible due to the functions injectivity).
        """
        if y == 0:
            return 0
        else:
            seg_nr = self.get_segment_nr_from_y(y)
            if seg_nr:
                a, b = self.func_segments[seg_nr]
                x = (y - b) / a
                if x > self.control_points[seg_nr][0]:
                    return x
    
    def get_segment_nr_from_x(self, x):
        """
        Returns the number of the function segment belonging
        to the x-coordinate *x*.
        """
        for nr in xrange(len(self.control_points) - 1):
            if self.control_points[nr][0] <= x <= self.control_points[nr + 1][0]:
                return nr
                break
            
    def get_segment_nr_from_y(self, y):
        """
        Returns the number of the function segment belonging
        to the y-coordinate *y*.
        """
        for nr in xrange(len(self.control_points) - 1):
            if self.control_points[nr][1] <= y <= self.control_points[nr + 1][1]:
                return nr
                break
