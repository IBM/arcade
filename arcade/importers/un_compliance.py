# Copyright 2020 IBM Corporation
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import os
import csv
import neomodel  # type: ignore
import pandas as pd  # type: ignore
import arcade.models.graph as graph


def export_compliance_data(astria_graph: neomodel.db, out_path: str) -> None:
    """Exports UN compliance data from ASTRIAGraph into a CSV file
    :param astria_graph: The database connection to ASTRIAGraph
    :param out_path: The path to save the CSV file to
    """
    query = ('MATCH (c:Compliance)'
             '<-[:SpaceObjectInstance2Compliance]-'
             '(so:SpaceObjectInstance) '
             'RETURN so.NoradId, c.calcTime, c.isCompliant')
    results, _ = astria_graph.cypher_query(query)
    result_columns = ['aso_id', 'calc_time', 'is_compliant']
    df = pd.DataFrame(data=results, columns=result_columns)
    # Get the most recently calculated compliance for each ASO
    latest_calc_time = df.groupby('aso_id').max('calc_time').reset_index()
    latest_calc_time.to_csv(out_path, index=False)


class UNComplianceImporter:
    """A class for importing UN compliance from ASTRIAGraph into the ARCADE
    neo4j database

    :param import_csv_path: The compliance CSV file exported from ASTRIAGraph
    """
    def __init__(self, import_csv_path: str) -> None:
        self.import_csv_path = import_csv_path
        self.data_source_node = graph.DataSource.get_or_create(
            {
                'name': 'UN - Compliance',
                'public': True
            }
        )[0]

    def run(self) -> None:
        """Imports the UN compliance data from the CSV file"""
        with open(self.import_csv_path) as csv_file:
            csv_reader = csv.DictReader(csv_file)
            for row in csv_reader:
                aso_node = graph.SpaceObject.find_one(norad_id=row['aso_id'])
                if aso_node is None:
                    continue
                compliance_nodes = aso_node.compliance.all()
                if compliance_nodes:
                    compliance_node = compliance_nodes[0]
                    compliance_node.is_compliant = bool(row['is_compliant'])
                    compliance_node.save()
                else:
                    compliance_node = graph.Compliance(
                        is_compliant=bool(row['is_compliant'])
                    )
                    compliance_node.save()
                    aso_node.compliance.connect(compliance_node)
                    compliance_node.from_data_source.connect(
                        self.data_source_node
                    )


if __name__ == '__main__':
    neomodel.config.DATABASE_URL = os.environ['NEO4J_URL']
    importer = UNComplianceImporter(os.environ['COMPLIANCE_CSV_PATH'])
    importer.run()
