// Display the graph for correctors' activity in a given book

function book_correctors_gr(manuscript, book) {

    // Based on http://redotheweb.com/DependencyWheel/

    d3.json("book_correctors.json?ms_id="+manuscript+"&bk="+book, function(error, data) {

        //~ var data = {
          //~ packageNames: ['Main', 'A', 'B'],
          //~ matrix: [[0, 1, 1], // Main depends on A and B
                   //~ [0, 0, 1], // A depends on B
                   //~ [0, 0, 0]] // B doesn't depend on A or Main
        //~ };

        var chart = d3.chart.dependencyWheel()
          .width(700)    // also used for height, since the wheel is in a a square
          .margin(150)   // used to display package names
          .padding(.02); // separating groups in the wheel

        d3.select('#graph')
          .datum(data)
          .call(chart);

    });
}
