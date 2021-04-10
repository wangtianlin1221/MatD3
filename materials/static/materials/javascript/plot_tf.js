'use strict';

function plot_tf(element, data_all, title) {
  const ctx = element.getContext('2d');
  const datasets = [];
  const colors = [
    'rgb(89,112,216)', 'rgb(100,194,78)', 'rgb(162,88,201)', 'rgb(175,182,56)',
    'rgb(210,71,153)', 'rgb(80,144,44)', 'rgb(202,141,217)', 'rgb(75,189,128)',
    'rgb(211,68,88)', 'rgb(77,191,183)', 'rgb(208,88,49)', 'rgb(94,152,211)',
    'rgb(214,155,70)', 'rgb(122,94,160)', 'rgb(153,178,109)', 'rgb(156,69,98)',
    'rgb(58,128,80)', 'rgb(223,131,154)', 'rgb(116,115,42)', 'rgb(170,106,64)'
  ]
  for (let i = 0; i < data_all.length; i++) {
    datasets.push({
      label: data_all[i]['space-group'],
      backgroundColor: colors[i],
      borderColor: colors[i],
      data: data_all[i]['values'],
      showLine: false
    });
  }
  const chart = new Chart(ctx, {
    type: 'scatter',
    data: {datasets: datasets},
    options: {
      title: {
        display: true,
        text: title,
        fontSize: 16,
      },
      scales: {
        xAxes: [{
          type: 'linear',
          scaleLabel: {
            display: true,
            labelString: 't_Ⅰ',
            fontSize: 14,
          },
        }],
        yAxes: [{
          type: 'linear',
          scaleLabel: {
            display: true,
            labelString: 't_IV/V',
            fontSize: 14,
          },
        }]
      },
      tooltips: {
      	callbacks: {
      		title: function(tooltipItem, data) {
      			var title = data_all[tooltipItem[0].datasetIndex]['compounds'][tooltipItem[0].index][0];
      			return title;
      		},
      		label: function(tooltipItem, data) {
      			var label = ["t_I:" + tooltipItem.xLabel, "t_IV/V:" + tooltipItem.yLabel];
      			return label;
      		}
      	}
      }
    }
  });
  
  element.onclick = function (evt) {
    const point = chart.getElementAtEvent(evt)[0];
    if (point !== undefined) {
      let compound = data_all[point._datasetIndex]['compounds'][point._index][1];
      // alert(point._datasetIndex);
      window.open('/materials/' + compound);
    }
    
  };
}

document
.getElementById('compound')
.addEventListener('change', function() {
  axios
    .get('/materials/tolerance-factor-chart/0/' + this.value)
    .then(response => {
      const plot_el = document.getElementById('shannon_tf_chart_1');
      plot_tf(plot_el, response['data']['data'], 'Shannon Based Tolerance Factor');
    });

  axios
    .get('/materials/tolerance-factor-chart/1/' + this.value)
    .then(response => {
      const plot_el = document.getElementById('experimental_tf_chart_1');
      plot_tf(plot_el, response['data']['data'], 'Experimental Tolerance Factor');
    });

  axios
    .get('/materials/tolerance-factor-chart/2/' + this.value)
    .then(response => {
      const plot_el = document.getElementById('averaged_tf_chart_1');
      plot_tf(plot_el, response['data']['data'], 'Averaged Tolerance Factor');
    });
});
document.getElementById('compound').dispatchEvent(new Event('change'));


function reset_tf_charts() {
  document.getElementById('shannon_tf_chart').hidden = true;
  document.getElementById('experimental_tf_chart').hidden = true;
  document.getElementById('averaged_tf_chart').hidden = true;

  document.getElementById('shannon_tf_chart').className = "col-md-4";
  document.getElementById('experimental_tf_chart').className = "col-md-4";
  document.getElementById('averaged_tf_chart').className = "col-md-4";
}

const shannon_tf_button = document.getElementById('shannon-tf-button');
shannon_tf_button.addEventListener('click', event => {
  event.preventDefault();
  reset_tf_charts();
  const plot_el = document.getElementById('shannon_tf_chart');
  plot_el.hidden = false;
  plot_el.className = "col-md-12";
});

const experimental_tf_button = document.getElementById('experimental-tf-button');
experimental_tf_button.addEventListener('click', event => {
  event.preventDefault();
  reset_tf_charts();
  const plot_el = document.getElementById('experimental_tf_chart');
  plot_el.hidden = false;
  plot_el.className = "col-md-12";
});

const averaged_tf_button = document.getElementById('averaged-tf-button');
averaged_tf_button.addEventListener('click', event => {
  event.preventDefault();
  reset_tf_charts();
  const plot_el = document.getElementById('averaged_tf_chart');
  plot_el.hidden = false;
  plot_el.className = "col-md-12";
});

const compared_button = document.getElementById('compared-button');
compared_button.addEventListener('click', event => {
  event.preventDefault();
  reset_tf_charts();
  document.getElementById('shannon_tf_chart').hidden = false;
  document.getElementById('experimental_tf_chart').hidden = false;
  document.getElementById('averaged_tf_chart').hidden = false;
});
