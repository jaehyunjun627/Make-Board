<%@ page language="java" contentType="text/html; charset=UTF-8"
    pageEncoding="UTF-8"%>
<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<title>Insert title here</title>
</head>
<body>


<%
   request.setCharacterEncoding("utf-8");
   %>
   
   <div align="center">
   <h2>Request Test</h2>
   <hr />
      <table width="400" border="1" cellspacing="1" cellpadding="5">
      <tr>
    <td width="50">이름</td>
    <td width="100"><%= request.getParameter("username") %></td>
</tr>

<tr>
    <td width="50">직업</td>
    <td width="100"><%= request.getParameter("job") %></td>
</tr>

<tr>
    <td width="50">관심분야</td>
    <td width="100">
        <%
            String[] favorite = request.getParameterValues("favorite");
            if (favorite != null) {
                for (String f : favorite) {
                    out.print(f + " ");
                }
            } else {
                out.print("선택 없음");
            }
        %>
    </td>
</tr>
      
      </table>
   </div>


</body>
</html>