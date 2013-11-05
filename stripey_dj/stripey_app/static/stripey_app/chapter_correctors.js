// Display the graph for correctors' activity in a given chapter

function chapter_correctors_gr(manuscript, book, chapter) {

    // Based on http://bl.ocks.org/mbostock/3886208
    var margin = {top: 5, right: 5, bottom: 30, left: 5},
        width = 800 - margin.left - margin.right,
        height = 200 - margin.top - margin.bottom;

    var x = d3.scale.ordinal()
        .rangeRoundBands([0, width], .1);

    var y = d3.scale.linear()
        .rangeRound([height, 0]);

    var color = d3.scale.ordinal()
        .range(["#e3f86e", "#f8ac6e", "#6ef8da", "#cccccc", "#f86eec", "#d0743c", "#ff8c00"]);

    var xAxis = d3.svg.axis()
        .scale(x)
        .orient("bottom")
        .tickFormat("");

    var yAxis = d3.svg.axis()
        .scale(y)
        .orient("left")
        .tickFormat("");

    var svg = d3.select("#graph").append("svg")
        .attr("width", width + margin.left + margin.right)
        .attr("height", height + margin.top + margin.bottom)
        .append("g")
        .attr("transform", "translate(" + margin.left + "," + margin.top + ")");

    d3.json("chapter_correctors.json?ms_id="+manuscript+"&bk="+book+"&ch="+chapter, function(error, data) {
        color.domain(data['hands']);

        x.domain(data['verses'].map(function(d) { return d[0]; }));
        y.domain([0, d3.max(data['verses'], function(d) { return d[1].length; })]);

        svg.append("g")
            .attr("class", "x axis")
            .attr("transform", "translate(0," + height + ")")
            .call(xAxis);

        svg.append("g")
            .attr("class", "y axis")
            .call(yAxis)
            .append("text")
            .attr("transform", "rotate(-90)")
            .attr("y", 6)
            .attr("dy", ".71em")
            .style("text-anchor", "end")
            .text("Correctors");

        var x0 = 0;
        data['verses'].forEach(function(d) {
            var y0 = 0;
            c = d[1].map(function(name) { return {name: name, y0: y0, y1: y0 += 1}; });
            var vs = d[0];
            var g = svg.append("g")
                .attr("class", "g")
                .attr("transform", function(d) { return "translate(" + x0 + ",0)"; });

            c.forEach(function(d) {
                g.append("rect")
                    .attr("width", x.rangeBand())
                    .attr("y", y(d.y1))
                    .attr("height", y(d.y0) - y(d.y1))
                    .style("fill", color(d.name))
                    .append("svg:title")
                    .text('Vs '+vs+' : ' +d.name);
            });
            x0 += x.rangeBand();
        });

        var verse = svg.selectAll(".verse")
            .data(data)
            .enter().append("g")
            .attr("class", "g")
            .attr("transform", function(d) { return "translate(" + x(d['verse'][0]) + ",0)"; });

        verse.selectAll("rect")
            .data(data, function(d) { return d.correctors; })
            .enter().append("rect")
            .attr("width", x.rangeBand())
            .attr("y", function(d) { return y(d.y1); })
            .attr("height", function(d) { return y(d.y0) - y(d.y1); })
            .style("fill", function(d) { return color(d.name); });

        var legend = svg.selectAll(".legend")
            .data(color.domain().slice().reverse())
            .enter().append("g")
            .attr("class", "legend")
            .attr("transform", function(d, i) { return "translate(0," + i * 20 + ")"; });

        legend.append("rect")
            .attr("x", width - 18)
            .attr("width", 18)
            .attr("height", 18)
            .style("fill", color);

        legend.append("text")
            .attr("x", width - 24)
            .attr("y", 9)
            .attr("dy", ".35em")
            .style("text-anchor", "end")
            .text(function(d) { return d; });

        //Draw the Rectangle
        //~ var rectangle = svg.append("rect")
                                            //~ .attr("x", 10)
                                            //~ .attr("y", 10)
                                            //~ .attr("width", 50)
                                            //~ .attr("height", 100);
    });


}
